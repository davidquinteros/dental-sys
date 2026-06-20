# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DentalSys — a multi-tenant SaaS MVP for managing a dental clinic (patients, appointments, clinical treatments, billing, and a calendar/odontogram). Backend: Flask (Python) + PostgreSQL. Frontend: Angular 18 (standalone components, signals). UI strings, route labels, and seed data are in Spanish.

The root `README.md` documents an earlier, single-tenant version of this app — it predates multi-tenancy (`Clinic`), RLS, the permissions module, consultorios, appointment types, calendar, and odontogram. Don't trust it for current architecture; this file and the code are authoritative.

## Commands

### Docker (primary workflow)
```bash
docker compose up -d --build       # starts db, backend (:5000), frontend (:4200)
docker compose logs -f backend     # tail backend logs
docker compose exec backend flask db migrate -m "message"   # create a migration
docker compose exec backend flask db upgrade                # apply migrations
docker compose exec backend flask seed                      # seed clinic #1 demo data
docker compose exec backend flask create-clinic --name "..." --admin-email "..." --admin-password "..."
docker compose exec backend python simulate_data.py         # ~2 months of fake activity for clinic #1 (NOT idempotent — reruns duplicate appointments/invoices)
```
`backend/entrypoint.sh` runs migrations (as the `dental_user` superuser-ish role) then `flask seed` then `flask run` (as the restricted `dental_app` role) automatically on container start — see "Multi-tenancy" below for why two DB roles exist.

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
No ESLint config is present.

### Single migration / one-off DB script
Migrations live in `backend/migrations/versions/`; create with `flask db migrate -m "..."` then hand-edit if Alembic's autogenerate misses something non-trivial (e.g. enabling RLS, see `a3f9c2d81e47_add_row_level_security.py`, is written by hand with raw `op.execute`).

## Architecture

### Multi-tenancy: two independent enforcement layers
Every clinic-scoped table (`users`, `patients`, `appointments`, `treatments`, `treatment_plans`, `invoices`, `payment_plans`, `consultorios`, `appointment_types`, `role_permissions`) has a `clinic_id`. Isolation between clinics is enforced twice, deliberately:

1. **ORM-level filter** — `backend/app/middleware/tenancy.py` registers a SQLAlchemy `do_orm_execute` session event that injects `clinic_id == g.clinic_id` into every SELECT, including ones triggered by lazy-loaded relationships. A route that forgets to filter manually still can't leak another clinic's data.
2. **Postgres RLS** — migration `a3f9c2d81e47_add_row_level_security.py` adds `FORCE ROW LEVEL SECURITY` policies on the same tables, keyed off the `app.current_clinic_id` / `app.bypass_rls` session GUCs. This is defense-in-depth in case a future code path uses raw SQL.

`g.clinic_id` is resolved once per request in `resolve_request_clinic()` (registered as a Flask `before_request` hook in `app/__init__.py`) from the JWT identity. Key consequences for anyone touching this code:
- `is_platform_admin` users get an unscoped session (`g.clinic_id = None`) — intentional, for cross-clinic platform staff.
- Users with no resolvable `clinic_id` are filtered on `NO_MATCH_CLINIC_ID = -1` (fails closed, matches nothing) rather than skipping the filter.
- A rare platform-wide lookup (e.g. email-uniqueness at signup, in `seeder.py`'s `_email_taken`) must opt out of *both* layers explicitly: `.execution_options(skip_clinic_filter=True)` for the ORM filter, and the `platform_wide_lookup()` context manager (or `_bypass_rls()` in CLI scripts) for RLS.
- The app connects to Postgres as two different roles: `dental_app` (restricted, no `BYPASSRLS`, used for runtime traffic — `DATABASE_URL`) and `dental_user` (owns the schema, used only for migrations — `MIGRATIONS_DATABASE_URL`). This split is required because RLS is silently bypassed for a table's owning role. See `create_app_role.sql` for the role/grants setup and `entrypoint.sh` for which URL is used when.
- `reset_db_clinic_context()` runs on `teardown_request` to force the connection back to fail-closed before it returns to the pool — otherwise a pooled connection could leak one user's clinic context into the next request that reuses it.

### RBAC: roles vs. per-clinic page permissions
There are two separate authorization mechanisms layered on top of each other:
- **Route-level role decorators** in `app/middleware/auth.py` (`admin_required`, `doctor_or_admin_required`, `clinical_access_required`, etc.) gate individual endpoints by `UserRole` (`admin`, `doctor`, `receptionist`, `assistant`, `guest`).
- **Page-level permissions** (`app/models/permission.py`: `Page` + `RolePermission`) let each clinic's admin customize which roles can view/create/edit/delete each app section, via the Permissions UI (`/permissions`, admin-only). `RolePermission` is clinic-scoped (each clinic gets its own matrix, seeded with sane defaults by `seed_pages()` in `app/utils/seeder.py`). The frontend's `roleGuard` (`frontend/src/app/core/guards/auth.guard.ts`) checks `route.data.pageKey` against `PermissionService.canView()`, which is populated from `GET /api/permissions/me` right after login (`AuthService.login()` chains into `PermissionService.load()`).

When adding a new app section: register it as a `Page` (typically via `STANDARD_PAGES` in `seeder.py` if it should exist for every clinic), add a route-level decorator on the backend endpoints, and add `data: { pageKey: '...' }` to the Angular route so `roleGuard` and the sidebar (which calls `accessiblePages()`) pick it up automatically.

### Backend structure
- `app/models/` — SQLAlchemy models, one file per domain (`clinic`, `user`, `patient`, `consultorio`, `appointment`, `appointment_type`, `treatment`, `billing`, `permission`). Every model exposes `to_dict()`; routes serialize through that rather than ad hoc dicts.
- `app/routes/` — one blueprint per domain, registered in `app/__init__.py` under `/api/<name>`. Endpoints document themselves via Swagger YAML docstrings (parsed by `flasgger`); the aggregate spec is served at `/api/docs/` using the shared schemas/security scheme defined in `app/swagger_spec.py`.
- `app/middleware/` — cross-cutting concerns only: `auth.py` (JWT + role decorators) and `tenancy.py` (multi-tenancy, see above). Not a place for business logic.
- `app/utils/seeder.py` — both the `flask seed` demo-data command (clinic #1) and `flask create-clinic` (onboard a real tenant: creates the `Clinic` row, default pages/permissions/appointment types, and first admin — no demo data).
- `simulate_data.py` and `init_db.py` are standalone scripts (not blueprints), run directly with `python` inside the container; `init_db.py` also has one-off `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` patches for columns added after the table already existed in some deployments — prefer a real Alembic migration for new schema changes instead of extending that pattern.

### Frontend structure
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
