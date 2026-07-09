# Recetario Estructurado Imprimible (FCLI-11) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the free-text `Treatment.prescriptions` field with a structured, printable recetario: a "¿Con receta?" switch + repeatable medication editor in the atención form, a structured display + "Imprimir receta" button in the atención detail, and a dedicated printable view — plus the clinic address/phone/logo needed for that view's header, editable from `admin-frontend`.

**Architecture:** Backend adds three additive JSON/text/boolean columns to `Treatment` (mirroring the existing `Patient.medical_history`/`odontogram` JSON-column pattern already used in this codebase) and three additive text columns to `Clinic`, plus a new `GET /api/clinic/info` endpoint so the clinic-facing frontend (which has zero existing access to `Clinic` data — that's normally `platform_admin_required`-gated) can read its own clinic's header info. Frontend adds a `FormArray`-based medication editor to the existing `treatment-form.component`, a structured display + print button to `treatment-detail.component`, and a brand-new, deliberately self-contained (`not embedded`, no new `@Input()`) `TreatmentRecetaComponent` at `/treatments/:id/receta` that fetches its own data and renders with `@media print` CSS, opened via `window.open(..., '_blank')`. `admin-frontend`'s existing clinic edit form gets three new fields for the header data.

**Tech Stack:** Flask + SQLAlchemy (backend), Angular 18 standalone components + Reactive Forms + signals (`frontend/`), Angular 18 standalone components + template-driven forms (`admin-frontend/`). No test framework in any of the three (see Global Constraints).

## Global Constraints

- **No automated test suite exists in this repo** (backend has no pytest files, neither frontend app has Karma/Jasmine spec files — confirmed in `CLAUDE.md`). Every task's verification step is a **manual check you actually perform and observe** — `flask shell` / Swagger UI / curl for backend, a live Puppeteer session against the running Docker frontend container for UI (see below). **Do not submit source-code review, a build/compile check, or "should work" as verification — those are not verification.** This exact failure mode happened repeatedly on the previous plan in this repo (every frontend task's first attempt was rejected for it) — front-load it now.
- **Live browser verification pattern (frontend tasks):** the `frontend`/`admin-frontend` Docker containers are already running. Install Puppeteer once per task session if not already present: `docker compose exec frontend sh -c "apk add --no-cache chromium && npm install --no-save puppeteer-core"` (same for `admin_frontend` service if touching that app), launch with `puppeteer.launch({ executablePath: '/usr/bin/chromium-browser', headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox', '--host-resolver-rules=MAP localhost:5000 backend:5000'] })`. Log in with existing seeded credentials (do not reseed/wipe the shared dev DB — check what already exists via the API first; create minimal fixtures via the authenticated API only if genuinely needed, and clean them up afterward, confirmed via a follow-up GET). Delete any stray script/screenshot files you create in the repo working tree before finishing (`git status --short` must show only your intended diff).
- Backend module changes require `docker compose restart backend` to take effect (gunicorn has no `--reload`); this also re-runs `entrypoint.sh`'s automatic `flask db upgrade` against `MIGRATIONS_DATABASE_URL`, which is how the new migration in Task 1 gets applied — no manual migration command needed.
- All UI strings are in Spanish, matching the existing app.
- Reuse the existing visual style (colors, `.form-card`/`.btn`/`.form-group` CSS conventions already in each file) — do not introduce a new visual language for this feature.
- Never `git commit`/`git push` without the user's explicit go-ahead for that specific commit — each task below ends with a commit step; pause and confirm with the user before running it rather than running it automatically.
- The doctor's signature line on the printable view is **`full_name` + `specialty` only** — do NOT include `license_number` (explicit user decision, overriding the original Jira ticket text which mentioned "matrícula").
- The clinic logo (`logo_url`) is a **plain text URL field** — there is no file-upload UI for it in this feature (explicit scope decision).

---

### Task 1: Backend — migration + `Treatment`/`Clinic` model changes

**Files:**
- Create: `backend/migrations/versions/b7e4f91a2c3d_add_recetario_estructurado.py`
- Modify: `backend/app/models/treatment.py:29-71` (`Treatment` columns + `to_dict`)
- Modify: `backend/app/models/clinic.py:10-78` (`Clinic` columns + `to_dict`)

**Interfaces:**
- Produces: `Treatment.to_dict()["has_prescription"]: bool`, `["medications"]: list[dict] | None`, `["prescription_notes"]: str | None`. `Clinic.to_dict()["address"]/["phone"]/["logo_url"]: str | None`. Every later task relies on these exact key names.

- [ ] **Step 1: Write the migration**

Create `backend/migrations/versions/b7e4f91a2c3d_add_recetario_estructurado.py`:

```python
"""add structured recetario fields to treatments and clinics

Revision ID: b7e4f91a2c3d
Revises: a994a6c8d690
Create Date: 2026-07-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e4f91a2c3d'
down_revision = 'a994a6c8d690'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('treatments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_prescription', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('medications', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('prescription_notes', sa.Text(), nullable=True))

    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.add_column(sa.Column('address', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('logo_url', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.drop_column('logo_url')
        batch_op.drop_column('phone')
        batch_op.drop_column('address')

    with op.batch_alter_table('treatments', schema=None) as batch_op:
        batch_op.drop_column('prescription_notes')
        batch_op.drop_column('medications')
        batch_op.drop_column('has_prescription')
```

- [ ] **Step 2: Add the columns and `to_dict()` fields to `Treatment`**

In `backend/app/models/treatment.py`, change:
```python
    prescriptions = db.Column(db.Text, nullable=True)
    next_steps = db.Column(db.Text, nullable=True)

    # Images / Attachments (stored as JSON array of file paths)
    attachments = db.Column(db.JSON, nullable=True)
```
to:
```python
    prescriptions = db.Column(db.Text, nullable=True)
    next_steps = db.Column(db.Text, nullable=True)

    # Structured recetario (FCLI-11) — additive; `prescriptions` above is kept as a
    # read-only legacy field for treatments created before this feature.
    has_prescription = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())
    medications = db.Column(db.JSON, nullable=True)  # [{name, concentration, form, quantity, dosage, duration}]
    prescription_notes = db.Column(db.Text, nullable=True)

    # Images / Attachments (stored as JSON array of file paths)
    attachments = db.Column(db.JSON, nullable=True)
```

Then change `to_dict()`:
```python
            "prescriptions": self.prescriptions,
            "next_steps": self.next_steps,
            "attachments": self.attachments,
```
to:
```python
            "prescriptions": self.prescriptions,
            "next_steps": self.next_steps,
            "has_prescription": self.has_prescription,
            "medications": self.medications,
            "prescription_notes": self.prescription_notes,
            "attachments": self.attachments,
```

- [ ] **Step 3: Add the columns and `to_dict()` fields to `Clinic`**

In `backend/app/models/clinic.py`, change:
```python
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default=db.true())
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # SaaS subscription tracking (platform-admin managed, manual billing — no payment gateway).
```
to:
```python
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default=db.true())
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Printable-header info (FCLI-11) — shown on the recetario print view.
    address = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    logo_url = db.Column(db.String(500), nullable=True)

    # SaaS subscription tracking (platform-admin managed, manual billing — no payment gateway).
```

Then change `to_dict()`:
```python
            "is_active": self.is_active,
            "subscription_tier_id": self.subscription_tier_id,
```
to:
```python
            "is_active": self.is_active,
            "address": self.address,
            "phone": self.phone,
            "logo_url": self.logo_url,
            "subscription_tier_id": self.subscription_tier_id,
```

- [ ] **Step 4: Restart backend and verify manually**

Run: `docker compose restart backend` (this re-runs `entrypoint.sh`, which applies the new migration via `MIGRATIONS_DATABASE_URL` automatically).

Verify via `flask shell`:
```
docker compose exec backend flask shell
```
```python
from app.models.treatment import Treatment
from app.models.clinic import Clinic
t = Treatment.query.first()
c = Clinic.query.first()
print('has_prescription' in t.to_dict() and 'medications' in t.to_dict() and 'prescription_notes' in t.to_dict() if t else 'no treatments in db')
print('address' in c.to_dict() and 'phone' in c.to_dict() and 'logo_url' in c.to_dict() if c else 'no clinics in db')
```
Expected: both print `True` (or the "no ... in db" message if empty — either way no exception, confirming the migration applied and the new columns/keys exist).

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add backend/migrations/versions/b7e4f91a2c3d_add_recetario_estructurado.py backend/app/models/treatment.py backend/app/models/clinic.py
git commit -m "feat(backend): add structured recetario fields to Treatment and Clinic"
```

---

### Task 2: Backend — `create_treatment`/`update_treatment` accept and validate recetario fields

**Files:**
- Modify: `backend/app/routes/treatments.py:1-320`

**Interfaces:**
- Consumes: `Treatment(has_prescription=..., medications=..., prescription_notes=...)` constructor kwargs (Task 1).
- Produces: `_validate_medications(medications: list) -> str | None` — a module-level helper other backend code could reuse if needed, though only this file's two routes call it.

- [ ] **Step 1: Add the `_validate_medications` helper**

In `backend/app/routes/treatments.py`, right after the module-level constants (after the `_EXT_BY_TYPE` dict, before the `# ─── TREATMENTS (Single sessions) ───` section header), add:

```python
def _validate_medications(medications) -> str | None:
    """Returns an error message if any medication is missing name/dosage, else None."""
    if not isinstance(medications, list):
        return "medications debe ser una lista"
    for med in medications:
        if not isinstance(med, dict) or not med.get("name") or not med.get("dosage"):
            return "Cada medicamento requiere nombre y dosis"
    return None
```

- [ ] **Step 2: Accept the fields in `create_treatment()`**

Add to the Swagger body schema — change:
```python
            prescriptions:
              type: string
            next_steps:
              type: string
```
(the one inside `create_treatment`'s docstring, around line 182-185) to:
```python
            prescriptions:
              type: string
            next_steps:
              type: string
            has_prescription:
              type: boolean
              default: false
            medications:
              type: array
              description: >
                Cada medicamento requiere al menos "name" y "dosage". Formato:
                [{name, concentration, form, quantity, dosage, duration}]
              items:
                type: object
            prescription_notes:
              type: string
              description: Indicaciones generales del recetario
```

Change the function body — from:
```python
    current = get_current_user()
    data = request.get_json()
    required = ["patient_id", "procedure"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    treatment = Treatment(
        clinic_id=current.clinic_id,
        patient_id=data["patient_id"],
        doctor_id=data.get("doctor_id", current.id),
        appointment_id=data.get("appointment_id"),
        treatment_plan_id=data.get("treatment_plan_id"),
        diagnosis=data.get("diagnosis"),
        procedure=data["procedure"],
        tooth_number=data.get("tooth_number"),
        tooth_surface=data.get("tooth_surface"),
        description=data.get("description"),
        clinical_notes=data.get("clinical_notes"),
        prescriptions=data.get("prescriptions"),
        next_steps=data.get("next_steps"),
    )
```
to:
```python
    current = get_current_user()
    data = request.get_json()
    required = ["patient_id", "procedure"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    medications = data.get("medications") or []
    med_error = _validate_medications(medications)
    if med_error:
        return jsonify({"error": med_error}), 400

    treatment = Treatment(
        clinic_id=current.clinic_id,
        patient_id=data["patient_id"],
        doctor_id=data.get("doctor_id", current.id),
        appointment_id=data.get("appointment_id"),
        treatment_plan_id=data.get("treatment_plan_id"),
        diagnosis=data.get("diagnosis"),
        procedure=data["procedure"],
        tooth_number=data.get("tooth_number"),
        tooth_surface=data.get("tooth_surface"),
        description=data.get("description"),
        clinical_notes=data.get("clinical_notes"),
        prescriptions=data.get("prescriptions"),
        next_steps=data.get("next_steps"),
        has_prescription=bool(data.get("has_prescription", False)),
        medications=medications,
        prescription_notes=data.get("prescription_notes"),
    )
```

- [ ] **Step 3: Accept the fields in `update_treatment()`**

Add the same four Swagger properties to `update_treatment`'s docstring body schema — change:
```python
            prescriptions:
              type: string
            next_steps:
              type: string
```
(the one inside `update_treatment`'s docstring, around line 280-283) to:
```python
            prescriptions:
              type: string
            next_steps:
              type: string
            has_prescription:
              type: boolean
            medications:
              type: array
              description: >
                Cada medicamento requiere al menos "name" y "dosage". Formato:
                [{name, concentration, form, quantity, dosage, duration}]
              items:
                type: object
            prescription_notes:
              type: string
```

Change the function body — from:
```python
    treatment = Treatment.query.get_or_404(treatment_id)
    data = request.get_json()

    fields = [
        "diagnosis", "procedure", "tooth_number", "tooth_surface",
        "description", "clinical_notes", "prescriptions", "next_steps",
    ]
    for field in fields:
        if field in data:
            setattr(treatment, field, data[field])
```
to:
```python
    treatment = Treatment.query.get_or_404(treatment_id)
    data = request.get_json()

    if "medications" in data:
        med_error = _validate_medications(data["medications"] or [])
        if med_error:
            return jsonify({"error": med_error}), 400

    fields = [
        "diagnosis", "procedure", "tooth_number", "tooth_surface",
        "description", "clinical_notes", "prescriptions", "next_steps",
        "has_prescription", "medications", "prescription_notes",
    ]
    for field in fields:
        if field in data:
            setattr(treatment, field, data[field])
```

(`update_treatment` stays under `@doctor_or_admin_required` — unchanged, no code edit needed there; this already satisfies "editar prescripciones permanece bajo doctor_or_admin_required" from the spec since medications is just one more field in the same guarded endpoint.)

- [ ] **Step 4: Restart backend and verify manually**

Run: `docker compose restart backend`

Verify via Swagger UI (`http://localhost:5000/api/docs/`) or curl, authenticated as medical staff:
1. `POST /api/treatments/` with `{"patient_id": <id>, "procedure": "Test", "has_prescription": true, "medications": [{"name": "Amoxicilina", "dosage": "1 cada 8h"}], "prescription_notes": "Tomar con alimentos"}` → expect `201` with those fields echoed back.
2. `POST /api/treatments/` with a medication missing `dosage` (e.g. `{"medications": [{"name": "X"}]}`) → expect `400` with `"error": "Cada medicamento requiere nombre y dosis"`.
3. `PUT /api/treatments/<id>` (the one created in step 1) with `{"medications": [{"name": "Ibuprofeno", "dosage": "1 cada 12h"}]}` → expect `200`, then `GET /api/treatments/<id>` confirms the change persisted.

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add backend/app/routes/treatments.py
git commit -m "feat(backend): accept and validate structured recetario fields on treatments"
```

---

### Task 3: Backend — `update_clinic` accepts `address`/`phone`/`logo_url`

**Files:**
- Modify: `backend/app/routes/platform_admin.py:268-366` (`update_clinic`)

**Interfaces:**
- Consumes: `Clinic.address`/`.phone`/`.logo_url` columns (Task 1).
- Produces: `PUT /api/platform/clinics/<id>` now accepts optional `address`/`phone`/`logo_url` string fields in its JSON body, applied via plain `setattr`-style assignment like `notes`.

- [ ] **Step 1: Add the Swagger body schema properties**

In `backend/app/routes/platform_admin.py`, in `update_clinic`'s docstring, change:
```python
            notes:
              type: string
            plan_started_at:
```
to:
```python
            notes:
              type: string
            address:
              type: string
            phone:
              type: string
            logo_url:
              type: string
            plan_started_at:
```

- [ ] **Step 2: Handle the fields in the function body**

Change:
```python
    if "notes" in data:
        clinic.notes = data["notes"]
    if "subscription_tier_id" in data:
```
to:
```python
    if "notes" in data:
        clinic.notes = data["notes"]
    if "address" in data:
        clinic.address = data["address"]
    if "phone" in data:
        clinic.phone = data["phone"]
    if "logo_url" in data:
        clinic.logo_url = data["logo_url"]
    if "subscription_tier_id" in data:
```

- [ ] **Step 3: Restart backend and verify manually**

Run: `docker compose restart backend`

Verify via Swagger UI or curl, authenticated as a platform admin:
1. `PUT /api/platform/clinics/<id>` with `{"address": "Av. Siempre Viva 123", "phone": "591-70000000", "logo_url": "https://example.com/logo.png"}` → expect `200` with those fields in the response's `clinic` object.
2. `GET /api/platform/clinics/<id>` → confirms persistence.
3. As a sanity check, confirm a **non**-platform-admin clinic user still gets `403` on this same route (unchanged behavior — `platform_admin_required` still gates the whole endpoint).

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add backend/app/routes/platform_admin.py
git commit -m "feat(backend): allow editing clinic address/phone/logo_url via platform admin"
```

---

### Task 4: Backend — new `GET /api/clinic/info` endpoint

**Files:**
- Create: `backend/app/routes/clinic.py`
- Modify: `backend/app/__init__.py:79-102` (blueprint registration)

**Interfaces:**
- Consumes: `Clinic.address`/`.phone`/`.logo_url`/`.name` columns (Task 1), `get_current_user()`/`clinical_access_required` (existing, `app/middleware/auth.py`).
- Produces: `GET /api/clinic/info` → `{"name": str, "address": str|null, "phone": str|null, "logo_url": str|null}` (200), or `404` if the current user has no `clinic_id` (e.g. a platform admin). This is the only clinic-data endpoint accessible from `frontend/` (the clinic-facing app) — `/api/platform/clinics/<id>` stays `platform_admin_required`-only, unchanged.

- [ ] **Step 1: Create the new blueprint**

Create `backend/app/routes/clinic.py`:

```python
from flask import Blueprint, jsonify
from app.middleware.auth import clinical_access_required, get_current_user
from app.models.clinic import Clinic

clinic_bp = Blueprint("clinic", __name__)


@clinic_bp.route("/info", methods=["GET"])
@clinical_access_required
def clinic_info():
    """
    Datos públicos de la clínica del usuario autenticado
    ---
    tags:
      - Clínica
    security:
      - BearerAuth: []
    description: >
      Devuelve solo los datos de encabezado (nombre, dirección, teléfono, logo) de la
      clínica del usuario autenticado — no expone estado de suscripción/facturación,
      que es exclusivo de /api/platform/*.
    responses:
      200:
        description: Datos de la clínica
        schema:
          type: object
          properties:
            name:
              type: string
            address:
              type: string
            phone:
              type: string
            logo_url:
              type: string
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Usuario sin clínica asignada
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    clinic = Clinic.query.get_or_404(current.clinic_id, description="Clínica no encontrada")
    return jsonify({
        "name": clinic.name,
        "address": clinic.address,
        "phone": clinic.phone,
        "logo_url": clinic.logo_url,
    }), 200
```

- [ ] **Step 2: Register the blueprint**

In `backend/app/__init__.py`, change:
```python
    from app.routes.appointment_types import appointment_types_bp
    from app.routes.platform_admin import platform_bp
```
to:
```python
    from app.routes.appointment_types import appointment_types_bp
    from app.routes.clinic import clinic_bp
    from app.routes.platform_admin import platform_bp
```

And change:
```python
    app.register_blueprint(appointment_types_bp, url_prefix="/api/appointment-types")
    app.register_blueprint(platform_bp, url_prefix="/api/platform")
```
to:
```python
    app.register_blueprint(appointment_types_bp, url_prefix="/api/appointment-types")
    app.register_blueprint(clinic_bp, url_prefix="/api/clinic")
    app.register_blueprint(platform_bp, url_prefix="/api/platform")
```

- [ ] **Step 3: Restart backend and verify manually**

Run: `docker compose restart backend`

Verify via Swagger UI or curl:
1. Log in as a regular clinic user (doctor/admin/receptionist/assistant, NOT a platform admin) and `GET /api/clinic/info` with that token → expect `200` with `name`/`address`/`phone`/`logo_url` matching that user's clinic (set via Task 3's endpoint first if the clinic has no address/phone/logo_url yet).
2. With the same token, confirm `GET /api/platform/clinics/<id>` still returns `403` (unchanged — this task adds a new route, it does not touch `platform_admin_required`).
3. Without any token, `GET /api/clinic/info` → expect `401`.

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add backend/app/routes/clinic.py backend/app/__init__.py
git commit -m "feat(backend): add GET /api/clinic/info for the clinic-facing frontend"
```

---

### Task 5: Frontend — TS models + `ClinicService`

**Files:**
- Modify: `frontend/src/app/core/models/index.ts:117-139` (`Treatment` interface, add `Medication`)
- Modify: `frontend/src/app/core/services/api.service.ts:1-9,255-285` (imports, new `ClinicService`)

**Interfaces:**
- Produces: `Medication { name: string; concentration?: string; form?: string; quantity?: string; dosage: string; duration?: string; }`, `Treatment.has_prescription: boolean`, `Treatment.medications?: Medication[]`, `Treatment.prescription_notes?: string`, `ClinicInfo { name: string; address?: string; phone?: string; logo_url?: string; }`, `ClinicService.getInfo(): Observable<ClinicInfo>` (calls `GET /api/clinic/info` from Task 4). Tasks 6-10 consume these exact names.

- [ ] **Step 1: Add `Medication` and extend `Treatment`**

In `frontend/src/app/core/models/index.ts`, change:
```typescript
// ─── Treatment Models ──────────────────────────────────────────────────────────
export type TreatmentPlanStatus = 'active' | 'completed' | 'cancelled' | 'on_hold';

export interface Treatment {
  id: number;
  patient_id: number;
  patient_name: string;
  doctor_id: number;
  doctor_name: string;
  appointment_id?: number;
  treatment_plan_id?: number;
  treatment_plan_name?: string;
  diagnosis?: string;
  procedure: string;
  tooth_number?: string;
  tooth_surface?: string;
  description?: string;
  clinical_notes?: string;
  prescriptions?: string;
  next_steps?: string;
  performed_at: string;
  created_at: string;
}
```
to:
```typescript
// ─── Treatment Models ──────────────────────────────────────────────────────────
export type TreatmentPlanStatus = 'active' | 'completed' | 'cancelled' | 'on_hold';

/** One medication line in a Treatment's structured recetario (FCLI-11). */
export interface Medication {
  name: string;
  concentration?: string;
  form?: string;
  quantity?: string;
  dosage: string;
  duration?: string;
}

export interface Treatment {
  id: number;
  patient_id: number;
  patient_name: string;
  doctor_id: number;
  doctor_name: string;
  appointment_id?: number;
  treatment_plan_id?: number;
  treatment_plan_name?: string;
  diagnosis?: string;
  procedure: string;
  tooth_number?: string;
  tooth_surface?: string;
  description?: string;
  clinical_notes?: string;
  prescriptions?: string;
  next_steps?: string;
  has_prescription: boolean;
  medications?: Medication[];
  prescription_notes?: string;
  performed_at: string;
  created_at: string;
}

/** Header info for the recetario print view — GET /api/clinic/info. */
export interface ClinicInfo {
  name: string;
  address?: string;
  phone?: string;
  logo_url?: string;
}
```

- [ ] **Step 2: Add `ClinicService`**

In `frontend/src/app/core/services/api.service.ts`, change the top imports:
```typescript
import {
  Patient, Appointment, Treatment, TreatmentPlan, TreatmentImage,
  Invoice, Payment, PaymentPlan, PaymentPlanInstallment, DashboardData, User, Consultorio, AppointmentTypeItem
} from '../models';
```
to:
```typescript
import {
  Patient, Appointment, Treatment, TreatmentPlan, TreatmentImage,
  Invoice, Payment, PaymentPlan, PaymentPlanInstallment, DashboardData, User, Consultorio, AppointmentTypeItem,
  ClinicInfo,
} from '../models';
```

Then, right after the `UserService` class closes (after its `resetPassword` method, before the `// ─── Appointment Types ───` comment), change:
```typescript
  resetPassword(id: number, password: string): Observable<{ message: string }> {
    return this.http.put<{ message: string }>(`${API}/users/${id}/reset-password`, { password });
  }
}

// ─── Appointment Types ─────────────────────────────────────────────────────────
```
to:
```typescript
  resetPassword(id: number, password: string): Observable<{ message: string }> {
    return this.http.put<{ message: string }>(`${API}/users/${id}/reset-password`, { password });
  }
}

// ─── Clinic (own-clinic header info, clinic-facing app) ───────────────────────
@Injectable({ providedIn: 'root' })
export class ClinicService {
  constructor(private http: HttpClient) {}

  getInfo(): Observable<ClinicInfo> {
    return this.http.get<ClinicInfo>(`${API}/clinic/info`);
  }
}

// ─── Appointment Types ─────────────────────────────────────────────────────────
```

- [ ] **Step 3: Verify the frontend still compiles**

Run: `docker compose exec frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json`
Expected: no new type errors (the two new interfaces and the new service are additive; `Treatment.has_prescription: boolean` as non-optional is a new required field on an interface only ever read from API responses in this codebase, never constructed as a literal in existing code, so no existing call site breaks).

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/core/models/index.ts frontend/src/app/core/services/api.service.ts
git commit -m "feat(frontend): add Medication/ClinicInfo models and ClinicService"
```

---

### Task 6: Frontend — `treatment-form.component.ts` recetario logic

**Files:**
- Modify: `frontend/src/app/features/treatments/treatment-form.component.ts`

**Interfaces:**
- Consumes: `Medication` (Task 5).
- Produces: `medications: FormArray` (public property, form control name `'medications'` inside `this.form`), `readonly medicationForms: string[]` (the fixed "Forma" catalog, last entry `'Otro'`), `addMedication(): void`, `removeMedication(i: number): void`, `onPrescriptionToggle(): void`. Task 7's template reads all of these by these exact names.

- [ ] **Step 1: Import `FormArray` and `Medication`**

Change:
```typescript
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { TreatmentService, PatientService, AppointmentService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, Treatment, Appointment, TreatmentPlan } from '../../core/models';
```
to:
```typescript
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { TreatmentService, PatientService, AppointmentService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, Treatment, Appointment, TreatmentPlan, Medication } from '../../core/models';
```

- [ ] **Step 2: Add the `medications` FormArray and `medicationForms` catalog, build the form without the old `prescriptions` control**

Change:
```typescript
  form: FormGroup;
  saving = signal(false);
  errorMsg = signal('');
  isEdit = signal(false);
  editingTreatment = signal<Treatment | null>(null);
  selectedPatient = signal<Patient | null>(null);
  patientResults = signal<Patient[]>([]);
  patientSearch = '';
  private searchTimeout: any;

  appointmentOptions = signal<Appointment[]>([]);
  planOptions = signal<TreatmentPlan[]>([]);
  loadingAppointments = signal(false);
  loadingPlans = signal(false);

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    private patientService: PatientService,
    private appointmentService: AppointmentService,
    public auth: AuthService,
  ) {
    this.form = this.fb.group({
      procedure: ['', Validators.required],
      tooth_number: [''],
      tooth_surface: [''],
      diagnosis: [''],
      description: [''],
      clinical_notes: [''],
      prescriptions: [''],
      next_steps: [''],
      appointment_id: [''],
      treatment_plan_id: [''],
    });
  }
```
to:
```typescript
  form: FormGroup;
  medications: FormArray;
  readonly medicationForms = [
    'Comprimido', 'Cápsula', 'Jarabe', 'Gotas', 'Inyectable',
    'Crema/Ungüento', 'Enjuague bucal', 'Otro',
  ];
  saving = signal(false);
  errorMsg = signal('');
  isEdit = signal(false);
  editingTreatment = signal<Treatment | null>(null);
  selectedPatient = signal<Patient | null>(null);
  patientResults = signal<Patient[]>([]);
  patientSearch = '';
  private searchTimeout: any;

  appointmentOptions = signal<Appointment[]>([]);
  planOptions = signal<TreatmentPlan[]>([]);
  loadingAppointments = signal(false);
  loadingPlans = signal(false);

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    private patientService: PatientService,
    private appointmentService: AppointmentService,
    public auth: AuthService,
  ) {
    this.medications = this.fb.array([]);
    this.form = this.fb.group({
      procedure: ['', Validators.required],
      tooth_number: [''],
      tooth_surface: [''],
      diagnosis: [''],
      description: [''],
      clinical_notes: [''],
      next_steps: [''],
      appointment_id: [''],
      treatment_plan_id: [''],
      has_prescription: [false],
      medications: this.medications,
      prescription_notes: [''],
    });
  }

  private newMedicationGroup(med?: Medication): FormGroup {
    const presetForms = this.medicationForms.slice(0, -1);
    const isOther = !!med?.form && !presetForms.includes(med.form);
    return this.fb.group({
      name: [med?.name ?? '', Validators.required],
      concentration: [med?.concentration ?? ''],
      form: [isOther ? 'Otro' : (med?.form ?? '')],
      form_custom: [isOther ? med!.form : ''],
      quantity: [med?.quantity ?? ''],
      dosage: [med?.dosage ?? '', Validators.required],
      duration: [med?.duration ?? ''],
    });
  }

  addMedication(): void {
    this.medications.push(this.newMedicationGroup());
  }

  removeMedication(i: number): void {
    this.medications.removeAt(i);
  }

  onPrescriptionToggle(): void {
    if (!this.form.get('has_prescription')?.value) {
      while (this.medications.length) this.medications.removeAt(0);
    }
  }
```

- [ ] **Step 3: Precharge `has_prescription`/`prescription_notes`/`medications` in edit mode, drop `prescriptions`**

Change:
```typescript
        this.form.patchValue({
          procedure: t.procedure,
          tooth_number: t.tooth_number ?? '',
          tooth_surface: t.tooth_surface ?? '',
          diagnosis: t.diagnosis ?? '',
          description: t.description ?? '',
          clinical_notes: t.clinical_notes ?? '',
          prescriptions: t.prescriptions ?? '',
          next_steps: t.next_steps ?? '',
        });
```
to:
```typescript
        this.form.patchValue({
          procedure: t.procedure,
          tooth_number: t.tooth_number ?? '',
          tooth_surface: t.tooth_surface ?? '',
          diagnosis: t.diagnosis ?? '',
          description: t.description ?? '',
          clinical_notes: t.clinical_notes ?? '',
          next_steps: t.next_steps ?? '',
          has_prescription: t.has_prescription,
          prescription_notes: t.prescription_notes ?? '',
        });
        (t.medications ?? []).forEach(m => this.medications.push(this.newMedicationGroup(m)));
```

- [ ] **Step 4: Build `medications` (with the "Otro" transform) into the submit payload, drop `prescriptions`**

Change:
```typescript
    this.saving.set(true);
    this.errorMsg.set('');
    const val = this.form.value;
    const clinicalFields = {
      procedure: val.procedure,
      tooth_number: val.tooth_number || null,
      tooth_surface: val.tooth_surface || null,
      diagnosis: val.diagnosis || null,
      description: val.description || null,
      clinical_notes: val.clinical_notes || null,
      prescriptions: val.prescriptions || null,
      next_steps: val.next_steps || null,
    };
```
to:
```typescript
    this.saving.set(true);
    this.errorMsg.set('');
    const val = this.form.value;
    const medications = this.medications.controls.map(c => {
      const g = c.value;
      return {
        name: g.name,
        concentration: g.concentration || null,
        form: g.form === 'Otro' ? (g.form_custom || null) : (g.form || null),
        quantity: g.quantity || null,
        dosage: g.dosage,
        duration: g.duration || null,
      };
    });
    const clinicalFields = {
      procedure: val.procedure,
      tooth_number: val.tooth_number || null,
      tooth_surface: val.tooth_surface || null,
      diagnosis: val.diagnosis || null,
      description: val.description || null,
      clinical_notes: val.clinical_notes || null,
      next_steps: val.next_steps || null,
      has_prescription: !!val.has_prescription,
      medications: val.has_prescription ? medications : [],
      prescription_notes: val.has_prescription ? (val.prescription_notes || null) : null,
    };
```

- [ ] **Step 5: Verify manually in the browser**

Run: `docker compose ps` to confirm `frontend` is up (restart if needed). Using the Puppeteer pattern from Global Constraints, log in and:
1. Navigate to a patient's "Nueva Atención" (embedded modal) or `/treatments/new?patient_id=<id>`. With no template changes yet (Task 7), drive the component directly via `window.ng.getComponent(domElement)` to confirm: `component.medications` is a `FormArray` starting empty; calling `component.addMedication()` pushes a group with `name`/`dosage` required; `component.medicationForms` is the 8-item array ending in `'Otro'`.
2. Confirm `component.onPrescriptionToggle()` empties `component.medications` when `component.form.get('has_prescription').setValue(false)` was just called.
3. TypeScript compile check: `docker compose exec frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json` → no errors.

- [ ] **Step 6: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/treatments/treatment-form.component.ts
git commit -m "feat(frontend): add structured medication FormArray to treatment form"
```

---

### Task 7: Frontend — `treatment-form.component.html` recetario UI

**Files:**
- Modify: `frontend/src/app/features/treatments/treatment-form.component.html`
- Modify: `frontend/src/app/features/treatments/treatment-form.component.css`

**Interfaces:**
- Consumes: `medications: FormArray`, `medicationForms: string[]`, `addMedication()`, `removeMedication(i)`, `onPrescriptionToggle()` (Task 6, all exact names).

- [ ] **Step 1: Replace the "Prescripciones / Medicamentos" textarea with a full-width "Notas Clínicas" field**

Change:
```html
        <div class="form-row">
          <div class="form-group">
            <label>Notas Clínicas</label>
            <textarea formControlName="clinical_notes" rows="3"
              placeholder="Observaciones clínicas adicionales, complicaciones, hallazgos..."></textarea>
          </div>
          <div class="form-group">
            <label>Prescripciones / Medicamentos</label>
            <textarea formControlName="prescriptions" rows="3"
              placeholder="Medicamentos recetados, dosis, indicaciones..."></textarea>
          </div>
        </div>
```
to:
```html
        <div class="form-group">
          <label>Notas Clínicas</label>
          <textarea formControlName="clinical_notes" rows="3"
            placeholder="Observaciones clínicas adicionales, complicaciones, hallazgos..."></textarea>
        </div>
```

- [ ] **Step 2: Add the "Recetario / Prescripción" card**

Change:
```html
    @if (errorMsg()) {
      <div class="alert-error">{{ errorMsg() }}</div>
    }
```
to:
```html
    <!-- Recetario / Prescripción -->
    <div class="form-card">
      <div class="form-card-header recetario-header">
        <div class="recetario-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5l7 7Z"/>
          </svg>
          Recetario / Prescripción
        </div>
        <label class="switch-label">
          <input type="checkbox" formControlName="has_prescription" (change)="onPrescriptionToggle()"/>
          ¿Con receta?
        </label>
      </div>
      @if (form.get('has_prescription')?.value) {
        <div class="form-body">
          @for (med of medications.controls; track $index; let i = $index) {
            <div class="medication-card" [formGroup]="$any(med)">
              <div class="medication-card-header">
                <span>Medicamento {{ i + 1 }}</span>
                <button type="button" class="remove-med-btn" (click)="removeMedication(i)">Eliminar</button>
              </div>
              <div class="form-row-3">
                <div class="form-group">
                  <label>Medicamento <span class="req">*</span></label>
                  <input formControlName="name" type="text" placeholder="Ej: Amoxicilina"/>
                </div>
                <div class="form-group">
                  <label>Concentración</label>
                  <input formControlName="concentration" type="text" placeholder="Ej: 500mg"/>
                </div>
                <div class="form-group">
                  <label>Forma</label>
                  <select formControlName="form">
                    <option value="">Seleccionar...</option>
                    @for (f of medicationForms; track f) {
                      <option [value]="f">{{ f }}</option>
                    }
                  </select>
                </div>
              </div>
              @if (med.get('form')?.value === 'Otro') {
                <div class="form-group">
                  <label>Especifique la forma</label>
                  <input formControlName="form_custom" type="text" placeholder="Ej: Parche transdérmico"/>
                </div>
              }
              <div class="form-row-3">
                <div class="form-group">
                  <label>Cantidad</label>
                  <input formControlName="quantity" type="text" placeholder="Ej: 1 caja x 12"/>
                </div>
                <div class="form-group">
                  <label>Dosis <span class="req">*</span></label>
                  <input formControlName="dosage" type="text" placeholder="Ej: 1 comprimido cada 8h"/>
                </div>
                <div class="form-group">
                  <label>Duración</label>
                  <input formControlName="duration" type="text" placeholder="Ej: 7 días"/>
                </div>
              </div>
            </div>
          }
          <button type="button" class="btn btn-secondary add-med-btn" (click)="addMedication()">
            + Agregar medicamento
          </button>
          <div class="form-group">
            <label>Indicaciones Generales</label>
            <textarea formControlName="prescription_notes" rows="2"
              placeholder="Indicaciones generales del tratamiento, forma de conservación, etc..."></textarea>
          </div>
        </div>
      }
    </div>

    @if (errorMsg()) {
      <div class="alert-error">{{ errorMsg() }}</div>
    }
```

- [ ] **Step 3: Add the CSS for the new elements**

In `frontend/src/app/features/treatments/treatment-form.component.css`, change:
```css
.form-actions { display: flex; justify-content: flex-end; gap: 12px; }
```
to:
```css
.recetario-header { justify-content: space-between; }
.recetario-title { display: flex; align-items: center; gap: 8px; }
.recetario-title svg { width: 18px; height: 18px; color: #718096; }
.switch-label { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; color: #4a5568; cursor: pointer; }
.switch-label input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }

.medication-card { border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
.medication-card-header { display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; font-weight: 600; color: #4a5568; margin-bottom: 10px; }
.remove-med-btn { background: none; border: none; color: #e53e3e; font-size: 12px; font-weight: 600; cursor: pointer; padding: 2px 6px; }
.remove-med-btn:hover { text-decoration: underline; }
.add-med-btn { align-self: flex-start; }

.form-actions { display: flex; justify-content: flex-end; gap: 12px; }
```

- [ ] **Step 4: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints: log in, open a patient's "Nueva Atención" (embedded modal, matching the ticket's requirement that this work identically embedded and routed — test at least one of the two, ideally both), and observe (extract actual DOM text/state, not a prediction):
1. The "Recetario / Prescripción" card renders with the "¿Con receta?" switch, initially unchecked and no medication editor visible.
2. Checking the switch reveals "+ Agregar medicamento" and "Indicaciones Generales"; clicking it adds a "Medicamento 1" card with Medicamento/Concentración/Forma/Cantidad/Dosis/Duración fields.
3. Selecting "Otro" in the "Forma" select reveals the "Especifique la forma" text input; selecting anything else hides it.
4. Submitting with a medication missing "Medicamento" or "Dosis" is blocked (form invalid, fields show the `.error`/`field-error` state — check `hasError()`'s existing wiring still works for these, or that the submit button correctly stays enabled/disabled per `saving()`/`selectedPatient()` as before, and the browser's own required-field validity state blocks it via `form.invalid`).
5. Submitting with valid data creates a treatment with `has_prescription: true` and the medications array — confirm via a follow-up `GET /api/treatments/<id>`.
6. Unchecking "¿Con receta?" removes all medication cards.

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/treatments/treatment-form.component.html frontend/src/app/features/treatments/treatment-form.component.css
git commit -m "feat(frontend): render structured medication editor in treatment form"
```

---

### Task 8: Frontend — `treatment-detail.component` structured display + "Imprimir Receta" button

**Files:**
- Modify: `frontend/src/app/features/treatments/treatment-detail.component.ts`
- Modify: `frontend/src/app/features/treatments/treatment-detail.component.html`
- Modify: `frontend/src/app/features/treatments/treatment-detail.component.css`

**Interfaces:**
- Consumes: `Treatment.has_prescription`/`.medications`/`.prescription_notes` (Task 5).
- Produces: `printReceta(): void` — opens `/treatments/<id>/receta` in a new tab. That route doesn't exist until Task 9-10; this task's own verification only needs to confirm the button renders correctly and constructs the right URL, not that the destination page renders (expected — the final whole-plan review will confirm the full click-through works end to end).

- [ ] **Step 1: Add `printReceta()`**

In `frontend/src/app/features/treatments/treatment-detail.component.ts`, change:
```typescript
  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'long', year: 'numeric' });
  }
  formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString('es-BO', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
}
```
to:
```typescript
  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'long', year: 'numeric' });
  }
  formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString('es-BO', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  printReceta(): void {
    window.open(`/treatments/${this.treatment()!.id}/receta`, '_blank');
  }
}
```

- [ ] **Step 2: Add the "Imprimir Receta" button**

Change:
```html
      <div class="actions">
        @if (treatment()!.treatment_plan_id) {
          <a [routerLink]="['/treatments/plans', treatment()!.treatment_plan_id]" class="btn btn-secondary">Ver Plan</a>
        }
        @if (!embedded) {
```
to:
```html
      <div class="actions">
        @if (treatment()!.treatment_plan_id) {
          <a [routerLink]="['/treatments/plans', treatment()!.treatment_plan_id]" class="btn btn-secondary">Ver Plan</a>
        }
        @if (treatment()!.has_prescription) {
          <button type="button" class="btn btn-secondary" (click)="printReceta()">🖨️ Imprimir Receta</button>
        }
        @if (!embedded) {
```

- [ ] **Step 3: Replace the prescriptions display with a structured list (with legacy fallback)**

Change:
```html
        @if (treatment()!.prescriptions) {
          <div class="info-section prescription">
            <h4>💊 Prescripciones</h4>
            <p>{{ treatment()!.prescriptions }}</p>
          </div>
        }
```
to:
```html
        @if (treatment()!.has_prescription && (treatment()!.medications?.length ?? 0) > 0) {
          <div class="info-section prescription">
            <h4>💊 Recetario</h4>
            @for (med of treatment()!.medications; track $index) {
              <div class="medication-row">
                <span class="med-name">{{ med.name }}{{ med.concentration ? ' — ' + med.concentration : '' }}</span>
                <span class="med-detail">{{ med.form || '—' }} · Cant. {{ med.quantity || '—' }} · Dosis: {{ med.dosage }}{{ med.duration ? ' · ' + med.duration : '' }}</span>
              </div>
            }
            @if (treatment()!.prescription_notes) {
              <p class="prescription-notes">{{ treatment()!.prescription_notes }}</p>
            }
          </div>
        } @else if (treatment()!.prescriptions) {
          <div class="info-section prescription">
            <h4>💊 Prescripciones</h4>
            <p>{{ treatment()!.prescriptions }}</p>
          </div>
        }
```

- [ ] **Step 4: Add the CSS for the medication list**

In `frontend/src/app/features/treatments/treatment-detail.component.css`, change:
```css
.info-section.prescription { border-left: 3px solid #9f7aea; }
.info-section.next { border-left: 3px solid #48bb78; }
```
to:
```css
.info-section.prescription { border-left: 3px solid #9f7aea; }
.info-section.next { border-left: 3px solid #48bb78; }
.medication-row { display: flex; flex-direction: column; gap: 2px; padding: 8px 0; border-bottom: 1px solid #f0f4f8; }
.medication-row:last-of-type { border-bottom: none; }
.med-name { font-size: 14px; font-weight: 600; color: #2d3748; }
.med-detail { font-size: 12px; color: #718096; }
.prescription-notes { font-size: 14px; color: #2d3748; margin: 10px 0 0; padding-top: 10px; border-top: 1px dashed #e2e8f0; white-space: pre-wrap; }
```

- [ ] **Step 5: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints, open the detail page/modal for a treatment created in Task 7's verification (which has `has_prescription: true` and real medications):
1. Confirm the "💊 Recetario" section shows each medication's name/concentration/form/quantity/dosage/duration as literal rendered text (extract and report the actual DOM text, not a prediction), and "Indicaciones Generales" if set.
2. Confirm the "🖨️ Imprimir Receta" button is visible, and clicking it (or inspecting its bound handler) opens a new tab/window targeting `/treatments/<id>/receta` — note this destination 404s or renders a blank route today since Task 9-10 haven't landed yet; that's expected, only confirm the URL is correct.
3. Open the detail for a treatment with `has_prescription: false` (or none set) — confirm no "Recetario" section and no print button appear (or the legacy `prescriptions` paragraph shows instead, if that treatment predates this feature and has old free-text data).

- [ ] **Step 6: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/treatments/treatment-detail.component.ts frontend/src/app/features/treatments/treatment-detail.component.html frontend/src/app/features/treatments/treatment-detail.component.css
git commit -m "feat(frontend): show structured recetario and print button in treatment detail"
```

---

### Task 9: Frontend — `TreatmentRecetaComponent` data fetching + route

**Files:**
- Create: `frontend/src/app/features/treatments/treatment-receta.component.ts`
- Modify: `frontend/src/app/features/treatments/treatments.routes.ts`

**Interfaces:**
- Consumes: `TreatmentService.getById(id)`, `PatientService.getById(id)`, `UserService.getDoctors()`, `ClinicService.getInfo()` (all existing/Task 5).
- Produces: `TreatmentRecetaComponent` with `loading: Signal<boolean>`, `error: Signal<string>`, `treatment: Signal<Treatment|null>`, `patient: Signal<Patient|null>`, `clinic: Signal<ClinicInfo|null>`, `doctorSpecialty: Signal<string>`, `formatDate(iso): string`, `print(): void`. Task 10's template reads all of these by these exact names. Route `:id/receta` registered in `treatments.routes.ts`.

- [ ] **Step 1: Create the component (data-fetching only; Task 10 adds the template content)**

Create `frontend/src/app/features/treatments/treatment-receta.component.ts`:

```typescript
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { TreatmentService, PatientService, UserService, ClinicService } from '../../core/services/api.service';
import { Treatment, Patient, ClinicInfo } from '../../core/models';

@Component({
  selector: 'app-treatment-receta',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './treatment-receta.component.html',
  styleUrl: './treatment-receta.component.css',
})
export class TreatmentRecetaComponent implements OnInit {
  loading = signal(true);
  error = signal('');
  treatment = signal<Treatment | null>(null);
  patient = signal<Patient | null>(null);
  clinic = signal<ClinicInfo | null>(null);
  doctorSpecialty = signal('');

  constructor(
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    private patientService: PatientService,
    private userService: UserService,
    private clinicService: ClinicService,
  ) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.treatmentService.getById(id).subscribe({
      next: res => {
        const t = res.treatment;
        this.treatment.set(t);
        forkJoin({
          patient: this.patientService.getById(t.patient_id),
          doctors: this.userService.getDoctors(),
          clinic: this.clinicService.getInfo(),
        }).subscribe({
          next: ({ patient, doctors, clinic }) => {
            this.patient.set(patient.patient);
            this.doctorSpecialty.set(doctors.doctors.find(d => d.id === t.doctor_id)?.specialty ?? '');
            this.clinic.set(clinic);
            this.loading.set(false);
          },
          error: () => { this.error.set('No se pudo cargar la información de la receta'); this.loading.set(false); },
        });
      },
      error: () => { this.error.set('Atención no encontrada'); this.loading.set(false); },
    });
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'long', year: 'numeric' });
  }

  print(): void {
    window.print();
  }
}
```

- [ ] **Step 2: Create a placeholder template/CSS so the component compiles** (Task 10 replaces both fully)

Create `frontend/src/app/features/treatments/treatment-receta.component.html`:
```html
<div class="receta-page">
  @if (loading()) {
    <p>Cargando...</p>
  } @else if (error()) {
    <p>{{ error() }}</p>
  } @else if (treatment() && patient() && clinic()) {
    <p>{{ treatment()!.procedure }} — {{ patient()!.full_name }} — {{ clinic()!.name }}</p>
  }
</div>
```

Create `frontend/src/app/features/treatments/treatment-receta.component.css`:
```css
.receta-page { max-width: 700px; margin: 0 auto; padding: 32px; }
```

- [ ] **Step 3: Register the route**

In `frontend/src/app/features/treatments/treatments.routes.ts`, change:
```typescript
  {
    path: ':id/edit',
    loadComponent: () =>
      import('./treatment-form.component').then(m => m.TreatmentFormComponent),
    canActivate: [roleGuard],
    data: { roles: ['admin', 'doctor'] },
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./treatment-detail.component').then(m => m.TreatmentDetailComponent),
  },
```
to:
```typescript
  {
    path: ':id/edit',
    loadComponent: () =>
      import('./treatment-form.component').then(m => m.TreatmentFormComponent),
    canActivate: [roleGuard],
    data: { roles: ['admin', 'doctor'] },
  },
  {
    path: ':id/receta',
    loadComponent: () =>
      import('./treatment-receta.component').then(m => m.TreatmentRecetaComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./treatment-detail.component').then(m => m.TreatmentDetailComponent),
  },
```

- [ ] **Step 4: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints, log in and navigate directly to `/treatments/<id>/receta` for the treatment created in Task 7 (has real medications + a linked patient + clinic with address/phone/logo_url set via Task 3's endpoint). Extract and report the actual rendered placeholder text — confirm it shows the real procedure name, real patient full name, and real clinic name (proving all three parallel fetches succeeded, not just that the page didn't crash). Also navigate to a nonexistent treatment id (e.g. `/treatments/999999/receta`) and confirm the "Atención no encontrada" error state renders instead of a blank page or unhandled exception in the console.

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/treatments/treatment-receta.component.ts frontend/src/app/features/treatments/treatment-receta.component.html frontend/src/app/features/treatments/treatment-receta.component.css frontend/src/app/features/treatments/treatments.routes.ts
git commit -m "feat(frontend): add TreatmentRecetaComponent data fetching and route"
```

---

### Task 10: Frontend — `TreatmentRecetaComponent` printable layout

**Files:**
- Modify: `frontend/src/app/features/treatments/treatment-receta.component.html`
- Modify: `frontend/src/app/features/treatments/treatment-receta.component.css`

**Interfaces:**
- Consumes: `loading`, `error`, `treatment`, `patient`, `clinic`, `doctorSpecialty`, `formatDate()`, `print()` (Task 9, all exact names). `Patient.age` (existing backend-computed field, already in the `Patient` TS interface — no client-side age calculation needed).

- [ ] **Step 1: Replace the placeholder template with the full printable layout**

Replace the entire contents of `frontend/src/app/features/treatments/treatment-receta.component.html` with:

```html
<div class="receta-page">
  @if (loading()) {
    <p>Cargando...</p>
  } @else if (error()) {
    <p class="error-msg">{{ error() }}</p>
  } @else if (treatment() && patient() && clinic()) {
    <header class="receta-header">
      @if (clinic()!.logo_url) {
        <img [src]="clinic()!.logo_url" alt="Logo" class="clinic-logo"/>
      }
      <div class="clinic-info">
        <h1>{{ clinic()!.name }}</h1>
        @if (clinic()!.address) { <p>{{ clinic()!.address }}</p> }
        @if (clinic()!.phone) { <p>Tel: {{ clinic()!.phone }}</p> }
      </div>
    </header>

    <section class="patient-info">
      <p><strong>Paciente:</strong> {{ patient()!.full_name }}</p>
      <p>
        @if (patient()!.age !== undefined && patient()!.age !== null) {
          <strong>Edad:</strong> {{ patient()!.age }} años ·
        }
        <strong>C.I.:</strong> {{ patient()!.document_number }}
      </p>
      <p><strong>Fecha:</strong> {{ formatDate(treatment()!.performed_at) }}</p>
    </section>

    <section class="rx-block">
      <h2 class="rx-symbol">℞</h2>
      @for (med of treatment()!.medications; track $index) {
        <div class="medication-item">
          <p class="med-name">{{ med.name }}{{ med.concentration ? ' — ' + med.concentration : '' }}</p>
          <p class="med-detail">
            {{ med.form || '—' }} · Cantidad: {{ med.quantity || '—' }} · Dosis: {{ med.dosage }}{{ med.duration ? ' · Duración: ' + med.duration : '' }}
          </p>
        </div>
      }
    </section>

    @if (treatment()!.prescription_notes) {
      <section class="notes-block">
        <h3>Indicaciones generales</h3>
        <p>{{ treatment()!.prescription_notes }}</p>
      </section>
    }

    <footer class="signature-block">
      <div class="signature-line"></div>
      <p class="doctor-name">{{ treatment()!.doctor_name }}</p>
      @if (doctorSpecialty()) { <p class="doctor-specialty">{{ doctorSpecialty() }}</p> }
    </footer>

    <div class="print-actions no-print">
      <button type="button" (click)="print()">Imprimir</button>
    </div>
  }
</div>
```

- [ ] **Step 2: Replace the placeholder CSS with the full print-aware layout**

Replace the entire contents of `frontend/src/app/features/treatments/treatment-receta.component.css` with:

```css
.receta-page { max-width: 700px; margin: 0 auto; padding: 32px; font-family: inherit; color: #1a202c; }
.error-msg { color: #c53030; font-size: 14px; }

.receta-header { display: flex; align-items: center; gap: 16px; border-bottom: 2px solid #2b6cb0; padding-bottom: 16px; margin-bottom: 20px; }
.clinic-logo { max-height: 64px; max-width: 120px; object-fit: contain; }
.clinic-info h1 { font-size: 18px; margin: 0 0 4px; color: #1a202c; }
.clinic-info p { font-size: 13px; color: #4a5568; margin: 0; }

.patient-info { margin-bottom: 20px; font-size: 14px; }
.patient-info p { margin: 4px 0; }

.rx-block { margin-bottom: 20px; }
.rx-symbol { font-size: 28px; color: #2b6cb0; margin: 0 0 12px; }
.medication-item { padding: 10px 0; border-bottom: 1px solid #e2e8f0; }
.medication-item:last-child { border-bottom: none; }
.med-name { font-size: 15px; font-weight: 600; margin: 0 0 2px; }
.med-detail { font-size: 13px; color: #4a5568; margin: 0; }

.notes-block { margin-bottom: 32px; font-size: 14px; }
.notes-block h3 { font-size: 13px; text-transform: uppercase; color: #718096; margin: 0 0 6px; }
.notes-block p { margin: 0; white-space: pre-wrap; }

.signature-block { margin-top: 48px; text-align: center; width: 260px; }
.signature-line { border-top: 1px solid #1a202c; margin-bottom: 6px; }
.doctor-name { font-size: 14px; font-weight: 600; margin: 0; }
.doctor-specialty { font-size: 12px; color: #4a5568; margin: 2px 0 0; }

.print-actions { margin-top: 24px; text-align: center; }
.print-actions button { padding: 10px 24px; border-radius: 8px; background: #2b6cb0; color: white; border: none; font-size: 14px; font-weight: 600; cursor: pointer; }

@media print {
  .no-print { display: none; }
  .receta-page { padding: 0; }
}

@page { margin: 16mm; }
```

- [ ] **Step 3: Verify manually in the browser (real, observed session), including the full click-through from `treatment-detail`**

Using the Puppeteer pattern from Global Constraints:
1. Navigate directly to `/treatments/<id>/receta` for the treatment used in Task 9's verification. Extract and report the actual rendered text for: clinic name/address/phone (and confirm the `<img>` tag's `src` matches `logo_url` if set), patient name/age/C.I., each medication's full line, "Indicaciones generales" text, and the doctor's name + specialty (confirm `license_number` does NOT appear anywhere in the rendered output — the user explicitly required signature = name + specialty only).
2. From the treatment's detail page/modal (Task 8), click "🖨️ Imprimir Receta" and confirm it opens this same view in a new tab with the same content — this closes the loop Task 8 left pending.
3. Confirm the "Imprimir" button has class `no-print` and is present in the normal (non-print) view.
4. If your Puppeteer session can emulate print media (`page.emulateMediaType('print')`), take a screenshot in print mode and confirm the "Imprimir" button is hidden and the layout has no leftover app chrome (nav/sidebar) — this component was built self-contained and never included in `AppComponent`'s "with-sidebar" wrapper, but confirm visually since this is the specific behavior the ticket calls out ("que @media print no imprima la aplicación completa").

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/treatments/treatment-receta.component.html frontend/src/app/features/treatments/treatment-receta.component.css
git commit -m "feat(frontend): render printable recetario layout"
```

---

### Task 11: `admin-frontend` — `Clinic` model + `PlatformService.updateClinic` fields

**Files:**
- Modify: `admin-frontend/src/app/core/models/index.ts:39-55` (`Clinic` interface)
- Modify: `admin-frontend/src/app/core/services/platform.service.ts:36-42` (`updateClinic`)

**Interfaces:**
- Produces: `Clinic.address`/`.phone`/`.logo_url: string | null` (matches backend `Clinic.to_dict()` from Task 1/3). `PlatformService.updateClinic(id, data)`'s `data` type now includes optional `address`/`phone`/`logo_url`. Task 12 consumes both.

- [ ] **Step 1: Extend the `Clinic` interface**

In `admin-frontend/src/app/core/models/index.ts`, change:
```typescript
export interface Clinic {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  subscription_tier_id: number | null;
```
to:
```typescript
export interface Clinic {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  address: string | null;
  phone: string | null;
  logo_url: string | null;
  subscription_tier_id: number | null;
```

- [ ] **Step 2: Extend `PlatformService.updateClinic`'s payload type**

In `admin-frontend/src/app/core/services/platform.service.ts`, change:
```typescript
  updateClinic(id: number, data: Partial<{
    name: string; is_active: boolean; subscription_tier_id: number | null;
    subscription_status: string; notes: string;
    plan_started_at: string | null; plan_expires_at: string | null;
  }>): Observable<{ clinic: Clinic; message: string }> {
```
to:
```typescript
  updateClinic(id: number, data: Partial<{
    name: string; is_active: boolean; subscription_tier_id: number | null;
    subscription_status: string; notes: string;
    plan_started_at: string | null; plan_expires_at: string | null;
    address: string | null; phone: string | null; logo_url: string | null;
  }>): Observable<{ clinic: Clinic; message: string }> {
```

- [ ] **Step 3: Verify the admin-frontend still compiles**

Run: `docker compose exec admin-frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json` (the service is named `admin-frontend` in `docker-compose.yml`, container name `dental_admin_frontend`).
Expected: no new type errors — the three new `Clinic` fields are non-optional additions to a type only ever populated from API responses, and `updateClinic`'s new payload fields are all optional (`Partial<{...}>`), so no existing call site breaks.

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add admin-frontend/src/app/core/models/index.ts admin-frontend/src/app/core/services/platform.service.ts
git commit -m "feat(admin-frontend): add address/phone/logo_url to Clinic model"
```

---

### Task 12: `admin-frontend` — `clinic-detail.component` address/phone/logo_url fields

**Files:**
- Modify: `admin-frontend/src/app/features/clinics/clinic-detail.component.ts`
- Modify: `admin-frontend/src/app/features/clinics/clinic-detail.component.html`

**Interfaces:**
- Consumes: `Clinic.address`/`.phone`/`.logo_url`, `PlatformService.updateClinic` (Task 11).

- [ ] **Step 1: Add the fields to `editForm` and `load()`**

In `admin-frontend/src/app/features/clinics/clinic-detail.component.ts`, change:
```typescript
  editForm = {
    name: '', is_active: true, subscription_tier_id: null as number | null, subscription_status: '',
    plan_started_at: '', plan_expires_at: '', notes: '',
  };
```
to:
```typescript
  editForm = {
    name: '', is_active: true, subscription_tier_id: null as number | null, subscription_status: '',
    plan_started_at: '', plan_expires_at: '', notes: '',
    address: '', phone: '', logo_url: '',
  };
```

Change:
```typescript
        this.editForm = {
          name: d.clinic.name,
          is_active: d.clinic.is_active,
          subscription_tier_id: d.clinic.subscription_tier_id,
          subscription_status: d.clinic.subscription_status,
          plan_started_at: this.toDateInput(d.clinic.plan_started_at),
          plan_expires_at: this.toDateInput(d.clinic.plan_expires_at),
          notes: d.clinic.notes || '',
        };
```
to:
```typescript
        this.editForm = {
          name: d.clinic.name,
          is_active: d.clinic.is_active,
          subscription_tier_id: d.clinic.subscription_tier_id,
          subscription_status: d.clinic.subscription_status,
          plan_started_at: this.toDateInput(d.clinic.plan_started_at),
          plan_expires_at: this.toDateInput(d.clinic.plan_expires_at),
          notes: d.clinic.notes || '',
          address: d.clinic.address || '',
          phone: d.clinic.phone || '',
          logo_url: d.clinic.logo_url || '',
        };
```

(`saveEdit()` already spreads `...this.editForm` into the `updateClinic()` call — no change needed there, the three new fields ride along automatically.)

- [ ] **Step 2: Add the fields to the view-mode display**

In `admin-frontend/src/app/features/clinics/clinic-detail.component.html`, change:
```html
        <div class="form-group">
          <label>Notas internas</label>
          <p>{{ detail()!.clinic.notes || '—' }}</p>
        </div>
      } @else {
```
to:
```html
        <div class="form-row">
          <div class="form-group"><label>Dirección</label><p>{{ detail()!.clinic.address || '—' }}</p></div>
          <div class="form-group"><label>Teléfono</label><p>{{ detail()!.clinic.phone || '—' }}</p></div>
        </div>
        <div class="form-group">
          <label>Logo (URL)</label>
          <p>{{ detail()!.clinic.logo_url || '—' }}</p>
        </div>
        <div class="form-group">
          <label>Notas internas</label>
          <p>{{ detail()!.clinic.notes || '—' }}</p>
        </div>
      } @else {
```

- [ ] **Step 3: Add the fields to the edit-mode form**

Change:
```html
          <div class="form-group">
            <label>Notas internas</label>
            <textarea name="notes" rows="3" [(ngModel)]="editForm.notes"></textarea>
          </div>
          <div class="form-row">
            <button type="submit" class="btn btn-primary" [disabled]="savingEdit()">
```
to:
```html
          <div class="form-row">
            <div class="form-group">
              <label>Dirección</label>
              <input type="text" name="address" [(ngModel)]="editForm.address" />
            </div>
            <div class="form-group">
              <label>Teléfono</label>
              <input type="text" name="phone" [(ngModel)]="editForm.phone" />
            </div>
          </div>
          <div class="form-group">
            <label>Logo (URL de la imagen)</label>
            <input type="text" name="logo_url" [(ngModel)]="editForm.logo_url" placeholder="https://..." />
          </div>
          <div class="form-group">
            <label>Notas internas</label>
            <textarea name="notes" rows="3" [(ngModel)]="editForm.notes"></textarea>
          </div>
          <div class="form-row">
            <button type="submit" class="btn btn-primary" [disabled]="savingEdit()">
```

- [ ] **Step 4: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints against the `admin-frontend` container (service `admin-frontend`, port 4300; install Puppeteer there too if not already present), log in as a platform admin and:
1. Open a clinic's detail page, click "Editar", fill in Dirección/Teléfono/Logo (URL), save. Confirm the view-mode display now shows the exact values you entered (extract and report the actual rendered text).
2. Reload the page and confirm the values persisted (re-fetched from the backend, not just client-side state).
3. Switch back to `frontend/` and repeat Task 9/10's `/treatments/<id>/receta` check for the same clinic — confirm the header now shows the address/phone/logo you just set here, closing the loop between the two apps.

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add admin-frontend/src/app/features/clinics/clinic-detail.component.ts admin-frontend/src/app/features/clinics/clinic-detail.component.html
git commit -m "feat(admin-frontend): edit clinic address/phone/logo_url"
```
