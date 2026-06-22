# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DentalSys — a multi-tenant SaaS MVP for managing a dental clinic (patients, appointments, clinical treatments, billing, and a calendar/odontogram). Backend: Flask (Python) + PostgreSQL. Two separate Angular 18 frontends share that one backend: `frontend/` (port 4200, used by clinic staff — patients/appointments/billing/etc., gated by the RBAC described below) and `admin-frontend/` (port 4300, used only by the SaaS operator to manage clinics/subscriptions — see "Platform administration" below). UI strings, route labels, and seed data are in Spanish.

The root `README.md` documents an earlier, single-tenant version of this app — it predates multi-tenancy (`Clinic`), RLS, the permissions module, consultorios, appointment types, calendar, and odontogram. Don't trust it for current architecture; this file and the code are authoritative.

## Working agreement

**Never `git commit` or `git push` automatically.** All commits and pushes are done manually by the user — staging/committing/pushing is never an implicit step of finishing a task, even after a working fix, even right before reporting completion. Prepare and describe changes; wait to be explicitly asked before committing or pushing.

## Commands

### Docker (primary workflow)
```bash
docker compose up -d --build       # starts db, backend (:5000), frontend (:4200), admin-frontend (:4300)
docker compose logs -f backend     # tail backend logs
docker compose exec backend flask db migrate -m "message"   # create a migration
docker compose exec backend flask db upgrade                # apply migrations
docker compose exec backend flask seed                      # seed clinic #1 demo data + default subscription tiers
docker compose exec backend flask create-clinic --name "..." --admin-email "..." --admin-password "..."
docker compose exec backend flask create-platform-admin --email "..." --password "..."   # bootstrap a SaaS-operator user (is_platform_admin=True, no clinic)
docker compose exec backend python simulate_data.py         # ~2 months of fake activity for clinic #1 (NOT idempotent — reruns duplicate appointments/invoices)
```
`backend/entrypoint.sh` runs migrations (as the `dental_user` superuser-ish role, via `MIGRATIONS_DATABASE_URL`) then `flask seed`, then execs `gunicorn` (as the restricted `dental_app` role, via `DATABASE_URL`) automatically on container start — see "Multi-tenancy" below for why two DB roles exist. Gunicorn has no `--reload` flag here (tuned to behave like prod even locally), so it loads every backend module once at boot: any `.py` change (routes, models, middleware) needs `docker compose restart backend` to actually take effect, even though the file is bind-mounted and visible inside the container immediately.

### Backend (Flask), run outside Docker
```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env        # then edit DATABASE_URL etc.
flask db upgrade
flask seed
flask run --port 5000
```
There is no automated test suite (no pytest files) and no linter configured for the backend — verify changes by exercising the API (e.g. via `/api/docs/`, the Swagger UI) or `flask shell`.

### Frontend (Angular), run outside Docker
```bash
cd frontend
npm install
npm start          # ng serve --port 4200
npm run build       # ng build
npm test            # karma/jasmine — no spec files currently exist in the repo
```
No ESLint config is present. `admin-frontend/` is a separate Angular app/`package.json` with the same commands, served on port 4300 (`npm start` there runs `ng serve --port 4300`).

### Single migration / one-off DB script
Migrations live in `backend/migrations/versions/`; create with `flask db migrate -m "..."` then hand-edit if Alembic's autogenerate misses something non-trivial (e.g. enabling RLS, see `a3f9c2d81e47_add_row_level_security.py`, is written by hand with raw `op.execute`).

## Architecture

### Multi-tenancy: two independent enforcement layers
Every clinic-scoped table (`users`, `patients`, `appointments`, `treatments`, `treatment_plans`, `invoices`, `payment_plans`, `consultorios`, `appointment_types`, `role_permissions`, `subscription_payments`) has a `clinic_id`. Isolation between clinics is enforced twice, deliberately:

1. **ORM-level filter** — `backend/app/middleware/tenancy.py`'s `_scoped_models()` list registers a SQLAlchemy `do_orm_execute` session event that injects `clinic_id == g.clinic_id` into every SELECT against those models, including ones triggered by lazy-loaded relationships. A route that forgets to filter manually still can't leak another clinic's data.
2. **Postgres RLS** — migration `a3f9c2d81e47_add_row_level_security.py` (plus `f3f85dc00800_add_rls_to_subscription_payments.py` for the table added later) adds `FORCE ROW LEVEL SECURITY` policies on the same tables, keyed off the `app.current_clinic_id` / `app.bypass_rls` session GUCs. This is defense-in-depth in case a future code path uses raw SQL.

**Whenever a new table gets a `clinic_id` column, it must be added to *both* lists** — `_scoped_models()` in `tenancy.py` and a migration enabling RLS on it (copy the pattern in `f3f85dc00800_...`). `subscription_payments` shipped without either for one day (2026-06-21) before this was caught and fixed; it was never actually exploitable (every route touching it was already gated by `platform_admin_required`, see "Platform administration" below), but don't rely on route-level gating alone — that's exactly the kind of single point of failure this dual-layer design exists to avoid. Tables that are genuinely platform-wide config with no `clinic_id` (e.g. `subscription_tiers`, `clinics` itself) correctly stay out of both lists.

`g.clinic_id` is resolved once per request in `resolve_request_clinic()` (registered as a Flask `before_request` hook in `app/__init__.py`) from the JWT identity. Key consequences for anyone touching this code:
- `is_platform_admin` users get an unscoped session (`g.clinic_id = None`, `g.rls_bypass = True`) — intentional, for cross-clinic platform staff (see "Platform administration" below).
- Users with no resolvable `clinic_id` are filtered on `NO_MATCH_CLINIC_ID = -1` (fails closed, matches nothing) rather than skipping the filter.
- A rare platform-wide lookup (e.g. email-uniqueness at signup, in `seeder.py`'s `_email_taken`) must opt out of *both* layers explicitly: `.execution_options(skip_clinic_filter=True)` for the ORM filter, and the `platform_wide_lookup()` context manager (or `_bypass_rls()` in CLI scripts) for RLS.
- The app connects to Postgres as two different roles: `dental_app` (restricted, no `BYPASSRLS`, used for runtime traffic — `DATABASE_URL`) and `dental_user` (owns the schema, used only for migrations — `MIGRATIONS_DATABASE_URL`). This split is required because RLS is silently bypassed for a table's owning role. See `create_app_role.sql` for the role/grants setup and `entrypoint.sh` for which URL is used when.
- The `app.current_clinic_id` / `app.bypass_rls` GUCs are re-stamped on *every* SQLAlchemy connection-pool checkout (`@event.listens_for(Pool, "checkout")` in `tenancy.py`), reading `g.clinic_id`/`g.rls_bypass` fresh at that moment — not set once per request via `db.session.commit()` like an earlier version did. A commit releases the connection back to the pool, so under real concurrency (gunicorn with multiple workers/threads) a later query in the same request could otherwise land on a different physical connection carrying another request's stale tenant context. There is no `teardown_request` GUC-reset hook anymore — every checkout already stamps fresh state, so there's nothing to leak between requests.

### RBAC: roles vs. per-clinic page permissions
There are two separate authorization mechanisms layered on top of each other:
- **Route-level role decorators** in `app/middleware/auth.py` (`admin_required`, `doctor_or_admin_required`, `clinical_access_required`, etc.) gate individual endpoints by `UserRole` (`admin`, `doctor`, `receptionist`, `assistant`, `guest`).
- **Page-level permissions** (`app/models/permission.py`: `Page` + `RolePermission`) let each clinic's admin customize which roles can view/create/edit/delete each app section, via the Permissions UI (`/permissions`, admin-only). `RolePermission` is clinic-scoped (each clinic gets its own matrix, seeded with sane defaults by `seed_pages()` in `app/utils/seeder.py`). The frontend's `roleGuard` (`frontend/src/app/core/guards/auth.guard.ts`) checks `route.data.pageKey` against `PermissionService.canView()`, which is populated from `GET /api/permissions/me` right after login (`AuthService.login()` chains into `PermissionService.load()`).

When adding a new app section: register it as a `Page` (typically via `STANDARD_PAGES` in `seeder.py` if it should exist for every clinic), add a route-level decorator on the backend endpoints, and add `data: { pageKey: '...' }` to the Angular route so `roleGuard` and the sidebar (which calls `accessiblePages()`) pick it up automatically. This `Page`/`RolePermission` system is **clinic-scoped configuration only** — it lets a clinic's own admin customize their own staff's access. It has nothing to do with platform-admin access (next section); never gate a platform-admin endpoint with a `Page`/role check, and never let a clinic-scoped route depend on `is_platform_admin`.

### Platform administration: a separate SaaS-operator layer
Distinct from everything above, there's a second, non-clinic-scoped layer for the people who run the SaaS itself (onboarding clinics, tracking subscription payments, suspending non-payers) — not to be mixed with clinic-facing code or the `Page`/`RolePermission` system, which is meaningless for staff who don't belong to any clinic:

- **`admin-frontend/`** is a wholly separate Angular app/codebase (own `package.json`, own routes, port 4300), not a section of `frontend/`. It has its own minimal `auth.service.ts` + `platform.service.ts` and its own `auth.guard.ts` — it does not use `frontend/`'s `PermissionService`/`roleGuard`/page-permission machinery at all.
- Both frontends authenticate against the same `POST /api/auth/login` (a user is just a `User` row; `is_platform_admin` is a boolean flag on it, not a different login flow or token type) — but every backend route `admin-frontend` calls lives in **`app/routes/platform_admin.py`** under `/api/platform/*`, gated by **`platform_admin_required`** (`app/middleware/auth.py`), which checks `user.is_platform_admin`. This is a different check from every other role decorator (`admin_required` etc.), which check `user.role` and are meaningless for platform staff (a platform admin's `role` is just `ADMIN` with no bearing on platform access; a clinic's own `ADMIN` must get a 403 from every `/api/platform/*` route).
- **Models**: `app/models/subscription.py` holds `SubscriptionTier` (a platform-wide plan/price list — no `clinic_id`, not RLS/ORM-scoped, analogous to a config table) and `SubscriptionPayment` (one row per manually-recorded SaaS payment from a clinic — has `clinic_id`, **is** RLS/ORM-scoped like any other tenant data, see "Multi-tenancy" above). `Clinic` itself carries the subscription state fields (`subscription_tier_id`, `subscription_status`, `trial_ends_at`, `next_payment_due_at`, `suspended_at`) directly, since the clinic *is* the subscriber — this is the one place tenant identity and billing state intentionally live together.
- Bootstrap a platform-admin user with `flask create-platform-admin` (`create_platform_admin()` in `seeder.py`) — creates a `User` with `clinic_id=None`, `is_platform_admin=True`. `flask seed` also seeds default `SubscriptionTier` rows (`seed_subscription_tiers()`).
- Rule of thumb for future platform features: code for the SaaS-operator layer (models, routes, frontend) stays in its own files/app, gated only by `platform_admin_required`/`is_platform_admin`; it may *read* clinic data (platform admins are intentionally unscoped) but a clinic-facing route must never reach into platform-admin models or routes.

### Backend structure
- `app/models/` — SQLAlchemy models, one file per domain (`clinic`, `subscription`, `user`, `patient`, `consultorio`, `appointment`, `appointment_type`, `treatment`, `billing`, `permission`). Every model exposes `to_dict()`; routes serialize through that rather than ad hoc dicts.
- `app/routes/` — one blueprint per domain, registered in `app/__init__.py` under `/api/<name>` (e.g. `platform_admin.py` → `platform_bp` → `/api/platform`). Endpoints document themselves via Swagger YAML docstrings (parsed by `flasgger`); the aggregate spec is served at `/api/docs/` using the shared schemas/security scheme defined in `app/swagger_spec.py`.
- `app/middleware/` — cross-cutting concerns only: `auth.py` (JWT + role decorators, including `platform_admin_required`) and `tenancy.py` (multi-tenancy, see above). Not a place for business logic.
- `app/utils/seeder.py` — `flask seed` (demo-data for clinic #1 + default subscription tiers), `flask create-clinic` (onboard a real tenant: creates the `Clinic` row, default pages/permissions/appointment types, and first admin — no demo data), and `flask create-platform-admin` (bootstrap a SaaS-operator user).
- `simulate_data.py` and `init_db.py` are standalone scripts (not blueprints), run directly with `python` inside the container; `init_db.py` also has one-off `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` patches for columns added after the table already existed in some deployments — prefer a real Alembic migration for new schema changes instead of extending that pattern.

### Frontend structure
This section is about `frontend/` (the clinic-facing app, port 4200). `admin-frontend/` (port 4300) is a separate, much smaller app — see "Platform administration" above — and does not follow any of this (no `Page`/permission system, no feature-per-backend-domain mirroring beyond `clinics`/`subscription-tiers`).
- `core/services/api.service.ts` holds one `@Injectable` service class per domain (`PatientService`, `AppointmentService`, `TreatmentService`, `BillingService`, `UserService`, `ConsultorioService`, `AppointmentTypeService`, `DashboardService`) — all in this single file, thin wrappers around `HttpClient` calls to the matching Flask blueprint.
- `core/services/auth.service.ts` holds auth state in Angular signals (`currentUser`, `isLoggedIn`) backed by `localStorage`; role-check computed signals (`isAdmin`, `canManageBilling`, etc.) mirror the backend's role groupings and are used to conditionally show UI, but are not a substitute for backend authorization.
- `core/interceptors/auth.interceptor.ts` attaches the JWT bearer token and transparently retries once on a 401 via `AuthService.refreshToken()`.
- `app.routes.ts` lazy-loads each feature (`loadComponent`/`loadChildren`); every protected child route carries `canActivate: [roleGuard]` and `data: { pageKey, roles? }` — `roles` is an extra hard gate on top of the page-permission check, used for sections that should never be configurable away from admin (e.g. `users`, `appointment-types`, `consultorios`).
- Feature modules under `features/` mirror the backend domains 1:1, plus a few frontend-only concerns: `calendar` (visual scheduling using `angular-calendar`), and `patients/odontogram.component.ts` + `medical-history.component.ts` (sub-views of a patient, not separate backend blueprints — they hit `PatientService.getOdontogram/saveOdontogram` and the patient's `medical_history` JSON column).
- When a form's fields are needed inside a modal/dialog elsewhere (e.g. creating a patient from the appointment form), embed the existing feature component with an `embedded` input rather than duplicating its fields inline — that's the established pattern in this codebase.

### Domain model notes
- `Appointment` can optionally link to a `TreatmentPlan` (multi-session treatments, with `session_number`) and to a `Consultorio` (room). `Treatment` and `Invoice` each have an optional 1:1 back-reference to the `Appointment` that produced them.
- `Invoice.recalculate()` is the single source of truth for `subtotal`/`total`/`balance`/`status` — call it after mutating `items`, `discount`, or `amount_paid` rather than computing those fields inline. `InvoiceStatus.PARTIAL` is legacy (kept for existing rows) — partial payments are no longer modeled as a separate invoice status, see `PaymentPlan` for multi-installment billing instead.
- `Patient.medical_history` and `Patient.odontogram` are untyped JSON columns (free-form clinical data / per-tooth state), not normalized tables.
