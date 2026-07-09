# Referencia a Plan de Tratamiento en Citas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a cita be optionally associated with a patient's active treatment plan, expose that link in the "Agendar Cita" form, and surface it as a "Plan" reference column/line in every table that lists appointments or treatments (citas list, dashboard, patient-detail Citas/Atenciones tabs), with a click-through to the existing plan-detail modal.

**Architecture:** The backend already has the FK (`Appointment.treatment_plan_id`) and accepts it on create — this plan (1) adds a denormalized `treatment_plan_name` to both `Appointment.to_dict()` and `Treatment.to_dict()` so the frontend never needs a second lookup, (2) makes `treatment_plan_id` editable via `PUT /appointments/<id>`, (3) adds `joinedload` to avoid N+1 queries now that `to_dict()` touches the relationship, and (4) wires the frontend form/tables to read and write these fields, reusing the existing `openPlanDetail()` modal in `patient-detail.component` for navigation (via a `planId` query param when linking from outside that component).

**Tech Stack:** Flask + SQLAlchemy (backend), Angular 18 standalone components + Reactive Forms + signals (frontend). No test framework in either (see Global Constraints).

## Global Constraints

- **No automated test suite exists in this repo** (backend has no pytest files, frontend has no Karma/Jasmine spec files — confirmed in `CLAUDE.md`). Every task's verification step is a **manual check** (`flask shell` / Swagger UI `/api/docs/` / curl for backend, a running `ng serve`/docker frontend for UI) — not an automated test run. Do not invent a test file.
- Backend module changes require `docker compose restart backend` to take effect (gunicorn has no `--reload`), per `CLAUDE.md`.
- All UI strings are in Spanish, matching the existing app.
- Never `git commit`/`git push` without the user's explicit go-ahead for that specific commit (see `CLAUDE.md` "Working agreement") — each task below ends with a commit step; pause and confirm with the user before running it rather than running it automatically.

---

### Task 1: Backend — serialize `treatment_plan_name` on Appointment and Treatment

**Files:**
- Modify: `backend/app/models/appointment.py:71-95` (`Appointment.to_dict`)
- Modify: `backend/app/models/treatment.py:49-70` (`Treatment.to_dict`)

**Interfaces:**
- Produces: `Appointment.to_dict()["treatment_plan_name"]: str | None` and `Treatment.to_dict()["treatment_plan_name"]: str | None` — both read `self.treatment_plan.name if self.treatment_plan else None`. Later tasks (frontend) rely on this exact key name.

- [ ] **Step 1: Add `treatment_plan_name` to `Appointment.to_dict()`**

In `backend/app/models/appointment.py`, in the `to_dict` method, add the new key right after `"treatment_plan_id"`:

```python
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.full_name if self.doctor else None,
            "consultorio_id": self.consultorio_id,
            "consultorio_name": self.consultorio.name if self.consultorio else None,
            "created_by_id": self.created_by_id,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "duration_minutes": self.duration_minutes,
            "appointment_type": self.appointment_type,
            "status": self.status.value,
            "treatment_plan_id": self.treatment_plan_id,
            "treatment_plan_name": self.treatment_plan.name if self.treatment_plan else None,
            "session_number": self.session_number,
            "reason": self.reason,
            "notes": self.notes,
            "cancellation_reason": self.cancellation_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "has_treatment": self.treatment is not None,
            "has_invoice": self.invoice is not None,
        }
```

- [ ] **Step 2: Add `treatment_plan_name` to `Treatment.to_dict()`**

In `backend/app/models/treatment.py`, in `Treatment.to_dict`, add the same key right after `"treatment_plan_id"`:

```python
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.full_name if self.doctor else None,
            "appointment_id": self.appointment_id,
            "treatment_plan_id": self.treatment_plan_id,
            "treatment_plan_name": self.treatment_plan.name if self.treatment_plan else None,
            "diagnosis": self.diagnosis,
            "procedure": self.procedure,
            "tooth_number": self.tooth_number,
            "tooth_surface": self.tooth_surface,
            "description": self.description,
            "clinical_notes": self.clinical_notes,
            "prescriptions": self.prescriptions,
            "next_steps": self.next_steps,
            "attachments": self.attachments,
            "performed_at": self.performed_at.isoformat() if self.performed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

- [ ] **Step 3: Restart backend and verify manually**

Run: `docker compose restart backend`

Then verify via `flask shell` (no fixtures needed — just confirms the key exists on any existing row, or on `None` safely if there are no rows yet):

Run: `docker compose exec backend flask shell`
```python
from app.models.appointment import Appointment
from app.models.treatment import Treatment
a = Appointment.query.first()
t = Treatment.query.first()
print('treatment_plan_name' in a.to_dict() if a else 'no appointments in db')
print('treatment_plan_name' in t.to_dict() if t else 'no treatments in db')
```
Expected: both print `True` (or the "no ... in db" message if the local DB is empty — either way, no `AttributeError`/exception).

- [ ] **Step 4: Commit**

Ask the user before running this — do not commit automatically.

```bash
git add backend/app/models/appointment.py backend/app/models/treatment.py
git commit -m "feat(backend): serialize treatment_plan_name on Appointment and Treatment"
```

---

### Task 2: Backend — allow editing `treatment_plan_id` via `PUT /appointments/<id>`

**Files:**
- Modify: `backend/app/routes/appointments.py:357-471` (`update_appointment`)

**Interfaces:**
- Consumes: nothing new from other tasks.
- Produces: `PUT /appointments/<id>` now accepts an optional `treatment_plan_id` (int or `null`) in its JSON body, applied via a plain `setattr` like the existing `session_number` field. No new response shape (still returns `appointment.to_dict()`, which now includes `treatment_plan_name` from Task 1).

- [ ] **Step 1: Add `treatment_plan_id` to the Swagger body schema**

In `backend/app/routes/appointments.py`, in `update_appointment`'s docstring `parameters` → body `schema.properties`, add a property next to `session_number` (around line 389-390):

```python
            session_number:
              type: integer
            treatment_plan_id:
              type: integer
              description: Plan de tratamiento asociado. Enviar null para desasociar.
```

- [ ] **Step 2: Add `treatment_plan_id` to the editable/locked-field set**

Change line 435 from:
```python
    editable_fields = {"scheduled_at", "consultorio_id", "duration_minutes", "reason", "notes", "session_number"}
```
to:
```python
    editable_fields = {"scheduled_at", "consultorio_id", "duration_minutes", "reason", "notes", "session_number", "treatment_plan_id"}
```

- [ ] **Step 3: Apply the field in the update loop**

Change line 455 from:
```python
    for field in ["duration_minutes", "reason", "notes", "session_number"]:
```
to:
```python
    for field in ["duration_minutes", "reason", "notes", "session_number", "treatment_plan_id"]:
```

- [ ] **Step 4: Restart backend and verify manually via Swagger UI**

Run: `docker compose restart backend`

Open `http://localhost:5000/api/docs/`, authorize with a valid token (log in via `POST /api/auth/login` first, e.g. an admin seeded by `flask seed`), then:
1. `PUT /api/appointments/<id>` (pick an existing appointment id) with body `{"treatment_plan_id": <some existing plan id for that patient>}`.
2. Confirm the response's `appointment.treatment_plan_id` and `appointment.treatment_plan_name` match what you sent.
3. `GET /api/appointments/<id>` and confirm the value persisted.
4. Repeat with `{"treatment_plan_id": null}` and confirm it clears back to `null`/`None`.

Expected: all three responses reflect the value sent, no 400/500.

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add backend/app/routes/appointments.py
git commit -m "feat(backend): allow editing treatment_plan_id via PUT /appointments/<id>"
```

---

### Task 3: Backend — add `joinedload(treatment_plan)` to listing queries

**Files:**
- Modify: `backend/app/routes/appointments.py:142-146` (`list_appointments`)
- Modify: `backend/app/routes/dashboard.py:118-121` (today's appointments query) and `:188-191` (calendar query)
- Modify: `backend/app/routes/treatments.py` (add `joinedload` import + `list_treatments` query, lines 1-10 and 76)
- Modify: `backend/app/routes/patients.py` (add imports + `patient_history`, lines 1-6 and 479-489)

**Interfaces:**
- Consumes: nothing new — this is a performance-only change (avoids one extra query per row now that `to_dict()` touches `self.treatment_plan`), not a behavior change.
- Produces: no new fields; existing `to_dict()` output from Task 1 is unaffected, just cheaper.

- [ ] **Step 1: `list_appointments` — add the option**

In `backend/app/routes/appointments.py`, change:
```python
    query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
    )
```
to:
```python
    query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
        joinedload(Appointment.treatment_plan),
    )
```
(`joinedload` is already imported at the top of this file.)

- [ ] **Step 2: `dashboard.py` — add the option to both queries**

In `backend/app/routes/dashboard.py`, change the today's-appointments query:
```python
    today_query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
    ).filter(
```
to:
```python
    today_query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
        joinedload(Appointment.treatment_plan),
    ).filter(
```

And the calendar query:
```python
    cal_query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
    ).filter(
```
to:
```python
    cal_query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
        joinedload(Appointment.treatment_plan),
    ).filter(
```

(Verify `joinedload` is already imported in `dashboard.py` — it is, since both queries above already use it.)

- [ ] **Step 3: `treatments.py` — import `joinedload` and use it in `list_treatments`**

In `backend/app/routes/treatments.py`, change the import block at the top:
```python
from flask import Blueprint, request, jsonify, Response
from app import db
from app.models.treatment import Treatment, TreatmentPlan, TreatmentPlanStatus
from app.models.treatment_image import TreatmentImage
from app.middleware.auth import medical_staff_required, clinical_access_required, doctor_or_admin_required, get_current_user
from app.utils import storage
from datetime import date
import uuid
```
to:
```python
from flask import Blueprint, request, jsonify, Response
from app import db
from app.models.treatment import Treatment, TreatmentPlan, TreatmentPlanStatus
from app.models.treatment_image import TreatmentImage
from app.middleware.auth import medical_staff_required, clinical_access_required, doctor_or_admin_required, get_current_user
from app.utils import storage
from datetime import date
from sqlalchemy.orm import joinedload
import uuid
```

Then in `list_treatments`, change:
```python
    query = Treatment.query
    if patient_id:
```
to:
```python
    query = Treatment.query.options(joinedload(Treatment.treatment_plan))
    if patient_id:
```

- [ ] **Step 4: `patients.py` — import models + `joinedload`, use in `patient_history`**

In `backend/app/routes/patients.py`, change the import block at the top:
```python
from flask import Blueprint, request, jsonify
from app import db
from app.models.patient import Patient
from app.middleware.auth import clinical_access_required, get_current_user
from datetime import date
```
to:
```python
from flask import Blueprint, request, jsonify
from app import db
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.treatment import Treatment
from app.middleware.auth import clinical_access_required, get_current_user
from datetime import date
from sqlalchemy.orm import joinedload
```

Then in `patient_history`, change:
```python
    appointments = patient.appointments.order_by(
        db.desc("scheduled_at")
    ).all()

    treatments = patient.treatments.order_by(
        db.desc("performed_at")
    ).all()
```
to:
```python
    appointments = patient.appointments.options(
        joinedload(Appointment.treatment_plan)
    ).order_by(
        db.desc("scheduled_at")
    ).all()

    treatments = patient.treatments.options(
        joinedload(Treatment.treatment_plan)
    ).order_by(
        db.desc("performed_at")
    ).all()
```

- [ ] **Step 5: Restart backend and verify manually**

Run: `docker compose restart backend`

Verify no regressions:
1. Via Swagger UI or curl, hit `GET /api/appointments/`, `GET /api/appointments/today`, `GET /api/dashboard/`, `GET /api/treatments/`, and `GET /api/patients/<id>/history`.
2. Expected: all return `200` with the same shape as before (just now including `treatment_plan_name` from Task 1), no `500` from the added `.options()`/`joinedload` calls.

- [ ] **Step 6: Commit**

Ask the user before running this.

```bash
git add backend/app/routes/appointments.py backend/app/routes/dashboard.py backend/app/routes/treatments.py backend/app/routes/patients.py
git commit -m "perf(backend): joinedload treatment_plan in appointment/treatment listings"
```

---

### Task 4: Frontend — add `treatment_plan_name` to the `Appointment` and `Treatment` TS models

**Files:**
- Modify: `frontend/src/app/core/models/index.ts:92-114` (`Appointment` interface)
- Modify: `frontend/src/app/core/models/index.ts:119-137` (`Treatment` interface)

**Interfaces:**
- Produces: `Appointment.treatment_plan_name?: string` and `Treatment.treatment_plan_name?: string` — later tasks (5-9) read this field directly off objects returned by `AppointmentService`/`TreatmentService`/`PatientService.getHistory()`.

- [ ] **Step 1: Add the field to `Appointment`**

In `frontend/src/app/core/models/index.ts`, change:
```typescript
export interface Appointment {
  id: number;
  patient_id: number;
  patient_name: string;
  doctor_id: number;
  doctor_name: string;
  consultorio_id?: number;
  consultorio_name?: string;
  created_by_id: number;
  scheduled_at: string;
  duration_minutes: number;
  appointment_type: string;
  status: AppointmentStatus;
  treatment_plan_id?: number;
  session_number?: number;
  reason?: string;
  notes?: string;
  cancellation_reason?: string;
  created_at: string;
  completed_at?: string;
  has_treatment: boolean;
  has_invoice: boolean;
}
```
to:
```typescript
export interface Appointment {
  id: number;
  patient_id: number;
  patient_name: string;
  doctor_id: number;
  doctor_name: string;
  consultorio_id?: number;
  consultorio_name?: string;
  created_by_id: number;
  scheduled_at: string;
  duration_minutes: number;
  appointment_type: string;
  status: AppointmentStatus;
  treatment_plan_id?: number;
  treatment_plan_name?: string;
  session_number?: number;
  reason?: string;
  notes?: string;
  cancellation_reason?: string;
  created_at: string;
  completed_at?: string;
  has_treatment: boolean;
  has_invoice: boolean;
}
```

- [ ] **Step 2: Add the field to `Treatment`**

Change:
```typescript
export interface Treatment {
  id: number;
  patient_id: number;
  patient_name: string;
  doctor_id: number;
  doctor_name: string;
  appointment_id?: number;
  treatment_plan_id?: number;
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

- [ ] **Step 3: Verify the frontend still compiles**

Run: `cd frontend && npx tsc --noEmit -p tsconfig.app.json` (or, if that config path doesn't match, whichever `tsconfig` the project already uses for `ng build` — check `angular.json` if unsure)
Expected: no new type errors introduced by the two added optional fields (adding an optional property never breaks existing consumers).

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/core/models/index.ts
git commit -m "feat(frontend): add treatment_plan_name to Appointment and Treatment models"
```

---

### Task 5: Frontend — appointment-form: load patient's active plans and add form controls

**Files:**
- Modify: `frontend/src/app/features/appointments/appointment-form.component.ts`

**Interfaces:**
- Consumes: `TreatmentService.getPlans(params)` → `Observable<{ treatment_plans: TreatmentPlan[] }>` and `TreatmentService.getPlan(id)` → `Observable<{ treatment_plan: TreatmentPlan }>` (both already exist in `api.service.ts`, unchanged).
- Produces: a new `patientPlans = signal<TreatmentPlan[]>([])` and a private `loadPatientPlans(patientId, includePlanId?)` method — Task 6 (the template) reads `patientPlans()` and calls `onPlanChange()`.

- [ ] **Step 1: Import `TreatmentService` and `TreatmentPlan`**

Change:
```typescript
import {
  AppointmentService, PatientService, UserService,
  ConsultorioService, AppointmentTypeService,
} from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Appointment, Patient, User, Consultorio, AppointmentTypeItem } from '../../core/models';
```
to:
```typescript
import {
  AppointmentService, PatientService, UserService,
  ConsultorioService, AppointmentTypeService, TreatmentService,
} from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Appointment, Patient, User, Consultorio, AppointmentTypeItem, TreatmentPlan } from '../../core/models';
```

- [ ] **Step 2: Add the `patientPlans` signal and inject `TreatmentService`**

Change:
```typescript
  doctors         = signal<User[]>([]);
  consultorios    = signal<Consultorio[]>([]);
  appointmentTypes = signal<AppointmentTypeItem[]>([]);
```
to:
```typescript
  doctors         = signal<User[]>([]);
  consultorios    = signal<Consultorio[]>([]);
  appointmentTypes = signal<AppointmentTypeItem[]>([]);
  patientPlans    = signal<TreatmentPlan[]>([]);
```

Change the constructor:
```typescript
  constructor(
    private fb: FormBuilder,
    private route: ActivatedRoute,
    private router: Router,
    private apptService: AppointmentService,
    private patientService: PatientService,
    private userService: UserService,
    private consultorioService: ConsultorioService,
    private apptTypeService: AppointmentTypeService,
    public auth: AuthService,
  ) {
    this.form = this.fb.group({
      doctor_id:        ['', Validators.required],
      consultorio_id:   ['', Validators.required],
      scheduled_at:     ['', Validators.required],
      duration_minutes: [30],
      appointment_type: ['', Validators.required],
      reason:           [''],
      notes:            [''],
    });
  }
```
to:
```typescript
  constructor(
    private fb: FormBuilder,
    private route: ActivatedRoute,
    private router: Router,
    private apptService: AppointmentService,
    private patientService: PatientService,
    private userService: UserService,
    private consultorioService: ConsultorioService,
    private apptTypeService: AppointmentTypeService,
    private treatmentService: TreatmentService,
    public auth: AuthService,
  ) {
    this.form = this.fb.group({
      doctor_id:         ['', Validators.required],
      consultorio_id:    ['', Validators.required],
      scheduled_at:      ['', Validators.required],
      duration_minutes:  [30],
      appointment_type:  ['', Validators.required],
      treatment_plan_id: [''],
      session_number:    [''],
      reason:            [''],
      notes:             [''],
    });
  }
```

- [ ] **Step 3: Add `loadPatientPlans()` and `onPlanChange()`**

Add these as new private/public methods, right after `clearPatient()`:

```typescript
  clearPatient(): void {
    this.selectedPatient.set(null);
    this.patientPlans.set([]);
    this.form.patchValue({ treatment_plan_id: '', session_number: '' });
  }

  private loadPatientPlans(patientId: number, includePlanId?: number | null): void {
    this.treatmentService.getPlans({ patient_id: patientId, status: 'active' }).subscribe(res => {
      const plans: TreatmentPlan[] = res.treatment_plans;
      if (includePlanId && !plans.some(p => p.id === includePlanId)) {
        this.treatmentService.getPlan(includePlanId).subscribe(r => {
          this.patientPlans.set([r.treatment_plan, ...plans]);
        });
      } else {
        this.patientPlans.set(plans);
      }
    });
  }

  onPlanChange(): void {
    if (!this.form.get('treatment_plan_id')?.value) {
      this.form.patchValue({ session_number: '' });
    }
  }
```

(This replaces the existing `clearPatient(): void { this.selectedPatient.set(null); }` one-liner — the rest of the file is unchanged.)

- [ ] **Step 4: Call `loadPatientPlans()` from `selectPatient()`**

Change:
```typescript
  selectPatient(p: Patient): void {
    this.selectedPatient.set(p);
    this.patientResults.set([]);
    this.patientSearch = '';
  }
```
to:
```typescript
  selectPatient(p: Patient): void {
    this.selectedPatient.set(p);
    this.patientResults.set([]);
    this.patientSearch = '';
    this.form.patchValue({ treatment_plan_id: '', session_number: '' });
    this.loadPatientPlans(p.id);
  }
```

- [ ] **Step 5: Call `loadPatientPlans()` from the three other places a patient becomes known**

In `ngOnInit`, change the embedded branch:
```typescript
    if (this.embedded) {
      if (this.presetPatient) this.selectedPatient.set(this.presetPatient);
      if (this.appointmentId) {
        this.isEdit.set(true);
        this.apptId = this.appointmentId;
        this.loadAppointment(this.apptId);
      }
```
to:
```typescript
    if (this.embedded) {
      if (this.presetPatient) {
        this.selectedPatient.set(this.presetPatient);
        this.loadPatientPlans(this.presetPatient.id);
      }
      if (this.appointmentId) {
        this.isEdit.set(true);
        this.apptId = this.appointmentId;
        this.loadAppointment(this.apptId);
      }
```

And the non-embedded `patient_id` query-param branch:
```typescript
    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => this.selectedPatient.set(res.patient));
    }
```
to:
```typescript
    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => {
        this.selectedPatient.set(res.patient);
        this.loadPatientPlans(res.patient.id);
      });
    }
```

- [ ] **Step 6: Precharge `treatment_plan_id`/`session_number` and load plans (incl. the current one) in `loadAppointment()`**

Change:
```typescript
  private loadAppointment(id: number, fetchPatient = false): void {
    this.apptService.getById(id).subscribe({
      next: res => {
        const a = res.appointment;
        this.form.patchValue({
          doctor_id:        a.doctor_id,
          consultorio_id:   a.consultorio_id ?? '',
          scheduled_at:     a.scheduled_at.substring(0, 16),
          duration_minutes: a.duration_minutes,
          appointment_type: a.appointment_type,
          reason:           a.reason,
          notes:            a.notes,
        });
        if (fetchPatient) {
          this.patientService.getById(a.patient_id).subscribe(pr => this.selectedPatient.set(pr.patient));
        }
        this.updatePreviewSlot();
      },
    });
  }
```
to:
```typescript
  private loadAppointment(id: number, fetchPatient = false): void {
    this.apptService.getById(id).subscribe({
      next: res => {
        const a = res.appointment;
        this.form.patchValue({
          doctor_id:         a.doctor_id,
          consultorio_id:    a.consultorio_id ?? '',
          scheduled_at:      a.scheduled_at.substring(0, 16),
          duration_minutes:  a.duration_minutes,
          appointment_type:  a.appointment_type,
          treatment_plan_id: a.treatment_plan_id ?? '',
          session_number:    a.session_number ?? '',
          reason:            a.reason,
          notes:             a.notes,
        });
        if (fetchPatient) {
          this.patientService.getById(a.patient_id).subscribe(pr => {
            this.selectedPatient.set(pr.patient);
            this.loadPatientPlans(pr.patient.id, a.treatment_plan_id);
          });
        } else {
          const patientId = this.selectedPatient()?.id ?? a.patient_id;
          this.loadPatientPlans(patientId, a.treatment_plan_id);
        }
        this.updatePreviewSlot();
      },
    });
  }
```

- [ ] **Step 7: Cast `treatment_plan_id`/`session_number` to `int | null` on submit**

Change:
```typescript
  onSubmit(): void {
    if (this.form.invalid || !this.selectedPatient()) {
      this.form.markAllAsTouched();
      if (!this.selectedPatient()) this.errorMsg.set('Seleccione un paciente');
      return;
    }
    this.saving.set(true);
    this.errorMsg.set('');
    const payload = { ...this.form.value, patient_id: this.selectedPatient()!.id };
    const req = this.isEdit()
```
to:
```typescript
  onSubmit(): void {
    if (this.form.invalid || !this.selectedPatient()) {
      this.form.markAllAsTouched();
      if (!this.selectedPatient()) this.errorMsg.set('Seleccione un paciente');
      return;
    }
    this.saving.set(true);
    this.errorMsg.set('');
    const raw = this.form.value;
    const payload = {
      ...raw,
      patient_id: this.selectedPatient()!.id,
      treatment_plan_id: raw.treatment_plan_id ? +raw.treatment_plan_id : null,
      session_number: raw.session_number ? +raw.session_number : null,
    };
    const req = this.isEdit()
```

- [ ] **Step 8: Verify manually in the browser**

Run: `docker compose up -d --build` (or `docker compose restart frontend` if already running), then in a browser at `http://localhost:4200`:
1. Go to a patient with at least one active `TreatmentPlan` (create one via the "Planes de Tratamiento" tab if none exists), click "Agendar Cita" from there (or `/appointments/new?patient_id=<id>`).
2. Confirm a "Plan de Tratamiento" dropdown appears listing that patient's active plans, and selecting one reveals a "N° de Sesión" input.
3. Submit with a plan selected — confirm no console/network errors and the created appointment can be re-opened for edit with the same plan/session pre-filled.
4. Submit with "Ninguno" selected — confirm the appointment is created with no plan (no regression for the common case).

Expected: all four checks pass with no TypeScript compile errors (`ng serve`'s terminal output stays clean).

- [ ] **Step 9: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/appointments/appointment-form.component.ts
git commit -m "feat(frontend): load and submit treatment_plan_id/session_number in appointment form"
```

---

### Task 6: Frontend — appointment-form: add the Plan/Session UI

**Files:**
- Modify: `frontend/src/app/features/appointments/appointment-form.component.html`

**Interfaces:**
- Consumes: `patientPlans()` and `onPlanChange()` from Task 5.

- [ ] **Step 1: Insert the Plan/Session row after the "Tipo de Cita" field**

Change:
```html
          <!-- Type (dynamic) -->
          <div class="form-group">
            <label>Tipo de Cita <span class="req">*</span></label>
            <select formControlName="appointment_type" [class.error]="hasError('appointment_type')">
              <option value="">Seleccionar tipo...</option>
              @for (t of appointmentTypes(); track t.id) {
                <option [value]="t.key">
                  {{ t.label }}
                </option>
              }
            </select>
            @if (hasError('appointment_type')) { <span class="field-error">Seleccione un tipo</span> }
          </div>

          <!-- Reason -->
```
to:
```html
          <!-- Type (dynamic) -->
          <div class="form-group">
            <label>Tipo de Cita <span class="req">*</span></label>
            <select formControlName="appointment_type" [class.error]="hasError('appointment_type')">
              <option value="">Seleccionar tipo...</option>
              @for (t of appointmentTypes(); track t.id) {
                <option [value]="t.key">
                  {{ t.label }}
                </option>
              }
            </select>
            @if (hasError('appointment_type')) { <span class="field-error">Seleccione un tipo</span> }
          </div>

          <!-- Treatment plan (optional) -->
          @if (patientPlans().length > 0) {
            <div class="form-row">
              <div class="form-group">
                <label>Plan de Tratamiento (opcional)</label>
                <select formControlName="treatment_plan_id" (change)="onPlanChange()">
                  <option value="">Ninguno</option>
                  @for (plan of patientPlans(); track plan.id) {
                    <option [value]="plan.id">{{ plan.name }}</option>
                  }
                </select>
              </div>
              @if (form.get('treatment_plan_id')?.value) {
                <div class="form-group">
                  <label>N° de Sesión (opcional)</label>
                  <input type="number" min="1" formControlName="session_number" placeholder="Ej. 3"/>
                </div>
              }
            </div>
          }

          <!-- Reason -->
```

- [ ] **Step 2: Verify manually in the browser**

Covered by Task 5 Step 8 (same form) — no separate verification needed beyond confirming the dropdown/input render as expected there.

- [ ] **Step 3: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/appointments/appointment-form.component.html
git commit -m "feat(frontend): render treatment plan/session fields in appointment form"
```

---

### Task 7: Frontend — appointments-list: add the "Plan" column

**Files:**
- Modify: `frontend/src/app/features/appointments/appointments-list.component.html`
- Modify: `frontend/src/app/features/appointments/appointments-list.component.css`

**Interfaces:**
- Consumes: `appt.treatment_plan_id`, `appt.treatment_plan_name`, `appt.session_number` (all already on `Appointment` as of Task 4).

- [ ] **Step 1: Add the column header**

Change:
```html
          <tr>
            <th>Fecha y Hora</th>
            <th>Paciente</th>
            <th>Médico</th>
            <th>Consultorio</th>
            <th>Tipo</th>
            <th>Duración</th>
            <th>Estado</th>
            <th>Factura</th>
            <th></th>
          </tr>
```
to:
```html
          <tr>
            <th>Fecha y Hora</th>
            <th>Paciente</th>
            <th>Médico</th>
            <th>Consultorio</th>
            <th>Tipo</th>
            <th>Plan</th>
            <th>Duración</th>
            <th>Estado</th>
            <th>Factura</th>
            <th></th>
          </tr>
```

- [ ] **Step 2: Add the column cell**

Change:
```html
              <td class="text-sm">{{ typeLabel(appt.appointment_type) }}</td>
              <td class="text-sm text-muted">{{ appt.duration_minutes }}min</td>
```
to:
```html
              <td class="text-sm">{{ typeLabel(appt.appointment_type) }}</td>
              <td>
                @if (appt.treatment_plan_id) {
                  <a [routerLink]="['/patients', appt.patient_id]" [queryParams]="{ tab: 'plans', planId: appt.treatment_plan_id }" class="patient-link">
                    {{ appt.treatment_plan_name }}{{ appt.session_number ? ' (sesión ' + appt.session_number + ')' : '' }}
                  </a>
                } @else {
                  <span class="text-muted">—</span>
                }
              </td>
              <td class="text-sm text-muted">{{ appt.duration_minutes }}min</td>
```

- [ ] **Step 3: Verify manually in the browser**

Go to `/appointments`. Confirm:
1. A "Plan" column appears between "Tipo" and "Duración".
2. Appointments with a `treatment_plan_id` show the plan name (+ session number if set) as a blue link; others show `—`.
3. Clicking the link navigates to `/patients/<id>?tab=plans&planId=<planId>` (the actual modal wiring is Task 9-10 — for now just confirm the URL is correct; the modal auto-open won't work yet until those tasks land).

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/appointments/appointments-list.component.html
git commit -m "feat(frontend): show treatment plan reference in the appointments list table"
```

---

### Task 8: Frontend — dashboard: add Plan reference to "Citas de Hoy" and "Próximas Citas"

**Files:**
- Modify: `frontend/src/app/features/dashboard/dashboard.component.html`
- Modify: `frontend/src/app/features/dashboard/dashboard.component.css`

**Interfaces:**
- Consumes: `appt.treatment_plan_id`, `appt.treatment_plan_name`, `appt.session_number` from `data()!.today.appointments` and `upcomingAppointments()` (both already typed as `Appointment[]`, unchanged by this task).

- [ ] **Step 1: Add the plan line to "Citas de Hoy"**

Change:
```html
                  <div class="appt-info">
                    <a class="patient-name patient-link" [routerLink]="['/patients', appt.patient_id]">{{ appt.patient_name }}</a>
                    <span class="appt-type">{{ appointmentTypeLabel(appt.appointment_type) }}</span>
                  </div>
```
to:
```html
                  <div class="appt-info">
                    <a class="patient-name patient-link" [routerLink]="['/patients', appt.patient_id]">{{ appt.patient_name }}</a>
                    <span class="appt-type">{{ appointmentTypeLabel(appt.appointment_type) }}</span>
                    @if (appt.treatment_plan_id) {
                      <a class="appt-plan" [routerLink]="['/patients', appt.patient_id]" [queryParams]="{ tab: 'plans', planId: appt.treatment_plan_id }">
                        {{ appt.treatment_plan_name }}{{ appt.session_number ? ' (sesión ' + appt.session_number + ')' : '' }}
                      </a>
                    }
                  </div>
```

- [ ] **Step 2: Add the plan line to "Próximas Citas"**

Change:
```html
                    <div class="upcoming-info">
                      <span class="patient-name">{{ appt.patient_name }}</span>
                      <span class="upcoming-meta">{{ formatTime(appt.scheduled_at) }} · Dr. {{ appt.doctor_name.split(' ')[0] }}</span>
                    </div>
```
to:
```html
                    <div class="upcoming-info">
                      <span class="patient-name">{{ appt.patient_name }}</span>
                      <span class="upcoming-meta">{{ formatTime(appt.scheduled_at) }} · Dr. {{ appt.doctor_name.split(' ')[0] }}</span>
                      @if (appt.treatment_plan_id) {
                        <a class="upcoming-plan" [routerLink]="['/patients', appt.patient_id]" [queryParams]="{ tab: 'plans', planId: appt.treatment_plan_id }">
                          {{ appt.treatment_plan_name }}{{ appt.session_number ? ' (sesión ' + appt.session_number + ')' : '' }}
                        </a>
                      }
                    </div>
```

- [ ] **Step 3: Add matching CSS**

In `frontend/src/app/features/dashboard/dashboard.component.css`, right after the existing `.appt-type` rule:
```css
.appt-type { display: block; font-size: 12px; color: #718096; }
```
add:
```css
.appt-plan { display: block; font-size: 12px; color: #2b6cb0; text-decoration: none; }
.appt-plan:hover { text-decoration: underline; }
```

And right after the existing `.upcoming-meta` rule:
```css
.upcoming-meta { display: block; font-size: 12px; color: #a0aec0; }
```
add:
```css
.upcoming-plan { display: block; font-size: 11px; color: #2b6cb0; text-decoration: none; margin-top: 2px; }
.upcoming-plan:hover { text-decoration: underline; }
```

- [ ] **Step 4: Verify manually in the browser**

Go to `/` (dashboard) as a user with at least one today/upcoming appointment linked to a plan. Confirm the plan name (+ session, if set) shows as a small blue link under both the "Citas de Hoy" and "Próximas Citas" entries, and appointments with no plan show nothing extra (no `—` needed here — this is a compact info line, not a table cell).

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/dashboard/dashboard.component.html frontend/src/app/features/dashboard/dashboard.component.css
git commit -m "feat(frontend): show treatment plan reference on the dashboard"
```

---

### Task 9: Frontend — patient-detail: add "Plan" column to Citas and Atenciones tabs

**Files:**
- Modify: `frontend/src/app/features/patients/patient-detail.component.html:96-202` (Citas + Atenciones tabs)
- Modify: `frontend/src/app/features/patients/patient-detail.component.css`

**Interfaces:**
- Consumes: `a.treatment_plan_id`/`a.treatment_plan_name`/`a.session_number` (Appointment, Citas tab) and `t.treatment_plan_id`/`t.treatment_plan_name` (Treatment, Atenciones tab) — both from Task 4. Calls the existing `openPlanDetail(planId: number): void` method (`patient-detail.component.ts:135-143`, unchanged by this task).

- [ ] **Step 1: Add the column to the Citas tab**

Change:
```html
              <thead>
                <tr>
                  <th>Fecha</th><th>Médico</th><th>Tipo</th><th>Estado</th><th>Notas</th><th class="col-actions">Acciones</th>
                </tr>
              </thead>
              <tbody>
                @for (a of appointments(); track a.id) {
                  <tr>
                    <td>{{ formatDateTime(a.scheduled_at) }}</td>
                    <td>{{ a.doctor_name }}</td>
                    <td>{{ typeLabel(a.appointment_type) }}</td>
                    <td>
```
to:
```html
              <thead>
                <tr>
                  <th>Fecha</th><th>Médico</th><th>Tipo</th><th>Plan</th><th>Estado</th><th>Notas</th><th class="col-actions">Acciones</th>
                </tr>
              </thead>
              <tbody>
                @for (a of appointments(); track a.id) {
                  <tr>
                    <td>{{ formatDateTime(a.scheduled_at) }}</td>
                    <td>{{ a.doctor_name }}</td>
                    <td>{{ typeLabel(a.appointment_type) }}</td>
                    <td>
                      @if (a.treatment_plan_id) {
                        <button type="button" class="plan-link-btn" (click)="openPlanDetail(a.treatment_plan_id)">
                          {{ a.treatment_plan_name }}{{ a.session_number ? ' (sesión ' + a.session_number + ')' : '' }}
                        </button>
                      } @else {
                        <span class="text-muted">—</span>
                      }
                    </td>
                    <td>
```

- [ ] **Step 2: Add the column to the Atenciones tab**

Change:
```html
              <thead>
                <tr><th class="col-date">Fecha</th><th>Pieza</th><th>Procedimiento</th><th>Diagnóstico</th><th>Próximos Pasos</th><th class="col-actions">Acciones</th></tr>
              </thead>
              <tbody>
                @for (t of treatments(); track t.id) {
                  <tr>
                    <td class="col-date">
                      <span class="cell-date">{{ formatDate(t.performed_at) }}</span>
                      <span class="cell-doctor">{{ t.doctor_name }}</span>
                    </td>
                    <td>{{ t.tooth_number || '—' }}</td>
                    <td><strong>{{ t.procedure }}</strong></td>
                    <td class="notes-cell">{{ t.diagnosis || '—' }}</td>
                    <td class="notes-cell">{{ t.next_steps || '—' }}</td>
                    <td class="col-actions">
```
to:
```html
              <thead>
                <tr><th class="col-date">Fecha</th><th>Pieza</th><th>Procedimiento</th><th>Plan</th><th>Diagnóstico</th><th>Próximos Pasos</th><th class="col-actions">Acciones</th></tr>
              </thead>
              <tbody>
                @for (t of treatments(); track t.id) {
                  <tr>
                    <td class="col-date">
                      <span class="cell-date">{{ formatDate(t.performed_at) }}</span>
                      <span class="cell-doctor">{{ t.doctor_name }}</span>
                    </td>
                    <td>{{ t.tooth_number || '—' }}</td>
                    <td><strong>{{ t.procedure }}</strong></td>
                    <td>
                      @if (t.treatment_plan_id) {
                        <button type="button" class="plan-link-btn" (click)="openPlanDetail(t.treatment_plan_id)">
                          {{ t.treatment_plan_name }}
                        </button>
                      } @else {
                        <span class="text-muted">—</span>
                      }
                    </td>
                    <td class="notes-cell">{{ t.diagnosis || '—' }}</td>
                    <td class="notes-cell">{{ t.next_steps || '—' }}</td>
                    <td class="col-actions">
```

- [ ] **Step 3: Add CSS for `.plan-link-btn` and `.text-muted`**

In `frontend/src/app/features/patients/patient-detail.component.css`, add (check first whether `.text-muted` already exists elsewhere in this file — if it does, skip re-adding it):
```css
.plan-link-btn { background: none; border: none; padding: 0; font: inherit; color: #2b6cb0; font-weight: 500; cursor: pointer; text-align: left; }
.plan-link-btn:hover { text-decoration: underline; }
.text-muted { color: #a0aec0; }
```

- [ ] **Step 4: Verify manually in the browser**

Open a patient with at least one appointment and one atención linked to a treatment plan. Confirm:
1. "Citas" tab shows a "Plan" column between "Tipo" and "Estado"; clicking the plan name opens the existing plan-detail modal directly (no navigation/page reload).
2. "Atenciones" tab shows a "Plan" column between "Procedimiento" and "Diagnóstico"; same click behavior.
3. Rows without a plan show `—` in both tabs.

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/patients/patient-detail.component.html frontend/src/app/features/patients/patient-detail.component.css
git commit -m "feat(frontend): show treatment plan reference in patient Citas and Atenciones tabs"
```

---

### Task 10: Frontend — patient-detail: deep-link `planId` query param to auto-open the plan modal

**Files:**
- Modify: `frontend/src/app/features/patients/patient-detail.component.ts:73-88` (`ngOnInit`)

**Interfaces:**
- Consumes: `openPlanDetail(planId: number): void` (already exists, unchanged).
- Produces: navigating to `/patients/<id>?tab=plans&planId=<planId>` (the pattern used by Tasks 7-8's links) now auto-opens that plan's detail modal on load.

- [ ] **Step 1: Read `planId` from the query params in `ngOnInit`**

Change:
```typescript
  ngOnInit(): void {
    const tab = this.route.snapshot.queryParamMap.get('tab');
    if (tab) this.activeTab.set(tab);

    const id = +this.route.snapshot.paramMap.get('id')!;
    this.patientService.getHistory(id).subscribe({
      next: res => {
        this.patient.set(res.patient);
        this.appointments.set(res.appointments);
        this.treatments.set(res.treatments);
        this.plans.set(res.treatment_plans);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
```
to:
```typescript
  ngOnInit(): void {
    const tab = this.route.snapshot.queryParamMap.get('tab');
    if (tab) this.activeTab.set(tab);

    const planId = this.route.snapshot.queryParamMap.get('planId');
    if (planId) this.openPlanDetail(+planId);

    const id = +this.route.snapshot.paramMap.get('id')!;
    this.patientService.getHistory(id).subscribe({
      next: res => {
        this.patient.set(res.patient);
        this.appointments.set(res.appointments);
        this.treatments.set(res.treatments);
        this.plans.set(res.treatment_plans);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
```

(`openPlanDetail` does its own independent `treatmentService.getPlan(planId, true)` fetch, so it doesn't need to wait for `getHistory()` to resolve — see `patient-detail.component.ts:135-143`.)

- [ ] **Step 2: Verify manually in the browser end-to-end**

1. From `/appointments` (Task 7) or the dashboard (Task 8), click a "Plan" link on an appointment that has one.
2. Confirm the browser navigates to `/patients/<id>?tab=plans&planId=<planId>`, the "Planes de Tratamiento" tab is active, and the plan-detail modal for that specific plan opens automatically (matching what `openPlanDetail()` already renders when triggered from within that tab).
3. Confirm navigating to the same patient page *without* a `planId` (e.g. via the sidebar) does not open any modal.

- [ ] **Step 3: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/patients/patient-detail.component.ts
git commit -m "feat(frontend): deep-link planId query param to auto-open the plan detail modal"
```
