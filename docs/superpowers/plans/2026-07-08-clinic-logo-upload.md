# Subida de Logo de Clínica Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the free-text `logo_url` field on the `admin-frontend` clinic edit page with a real file upload, storing the image in the same **private** Supabase Storage bucket already used for clinical photos (FCLI-10), served only through authenticated endpoints — never a public URL.

**Architecture:** Backend reuses FCLI-10's existing `_read_upload_or_error()` validation helper (imported across blueprints) for a new `POST /api/platform/clinics/<id>/logo` upload route, storing bytes at a stable per-clinic path (`clinic_{id}/logo.jpg`, upserted on every upload — no orphans, no delete endpoint needed). Two GET routes serve the bytes back — `GET /api/clinic/logo` (self-scoped, for `frontend/`) and `GET /api/platform/clinics/<id>/logo` (id-scoped, for `admin-frontend`) — sharing one internal streaming helper. `Clinic.logo_url` is repurposed: it now holds the internal storage path (backend-written only, no longer editable via the general `PUT /api/platform/clinics/<id>` JSON body), and every consumer (both apps) fetches the image as an authenticated `Blob` and displays it via an object URL — the same pattern `treatment-images.component.ts` already established.

**Tech Stack:** Flask + `requests` (backend, reusing `app/utils/storage.py` unchanged), Angular 18 signals + `DomSanitizer` (both frontends).

## Global Constraints

- **No automated test suite exists in this repo.** Every task's verification step is a manual check you actually perform and observe — real API calls (backend tasks) or a real Puppeteer browser session (frontend tasks). Source-code inspection, "it compiled," or "verified in bundle" are explicitly NOT acceptable substitutes and will be rejected — this exact failure mode happened repeatedly on the previous plan in this repo (FCLI-11), sometimes multiple rounds per task, even after credentials were handed over directly in the dispatch prompt. Do not repeat it.
- **Live browser verification pattern:** both `frontend` (port 4200) and `admin-frontend` (port 4300) Docker containers are already running. Puppeteer is likely already installed in both containers from earlier work this session — check first (`docker compose exec frontend sh -c "ls node_modules/puppeteer-core"` / same for `admin-frontend`) before reinstalling. If missing: `docker compose exec <service> sh -c "apk add --no-cache chromium && npm install --no-save puppeteer-core"`, launched with `--host-resolver-rules=MAP localhost:5000 backend:5000`. **Working credentials:** clinic-facing app (`frontend`, port 4200) → `admin@clinica.com` / `Admin2025!`. `admin-frontend` (port 4300) → a platform-admin account already exists in this environment (do not create a new one unless a search genuinely turns up none — check via `flask shell` for a `User` row with `is_platform_admin=True`). Do NOT reseed/wipe the shared dev DB.
- **Storage must be configured to test uploads.** Before attempting a live upload, verify `storage.is_configured()` is `True` (e.g. `docker compose exec backend flask shell` → `from app.utils import storage; storage.is_configured()`). If `False`, report this plainly as an environment limitation rather than fabricating a success — the code can still be reviewed against its Swagger docs/error-path behavior (which should correctly return `503`).
- Backend module changes require `docker compose restart backend` to take effect.
- `logo_url` on `Clinic` now holds an **internal storage path** (e.g. `"clinic_3/logo.jpg"`), not a URL — do not expose it to a client as something to bind directly into `<img src>`; every consumer must fetch it as an authenticated `Blob` via the dedicated `GET` endpoints.
- Never `git commit`/`git push` without the user's explicit go-ahead for that specific commit — each task below ends with a commit step; pause and confirm with the user before running it. Do NOT run `git checkout`/`git clean`/`git reset` on the working tree at any point during verification — this exact repo has had unrelated uncommitted changes wiped by some git action during prior live-verification sessions this same day; only `git add`/`git commit` the files each task is responsible for.

---

### Task 1: Backend — clinic logo upload endpoint

**Files:**
- Modify: `backend/app/routes/platform_admin.py:1-12` (imports), `:378-379` (insert new route after `update_clinic`)

**Interfaces:**
- Consumes: `_read_upload_or_error() -> (data, content_type) | (None, (response, status))` (existing, `backend/app/routes/treatments.py:700-722`, imported cross-blueprint), `storage.upload_object(path, data, content_type)` / `storage.StorageError` (existing, `backend/app/utils/storage.py`, unchanged).
- Produces: `POST /api/platform/clinics/<id>/logo` → `{"clinic": {...}, "message": "Logo actualizado"}` (200), writes `Clinic.logo_url = f"clinic_{id}/logo.jpg"`. Task 2's serving endpoints read this same column/path convention.

- [ ] **Step 1: Add the imports**

In `backend/app/routes/platform_admin.py`, change:
```python
import secrets
import string
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from app import db
from app.models.clinic import Clinic
from app.models.user import User, UserRole
from app.models.subscription import SubscriptionTier, SubscriptionPayment, SubscriptionStatus
from app.middleware.auth import platform_admin_required, get_current_user
from app.utils.seeder import create_clinic
```
to:
```python
import secrets
import string
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from app import db
from app.models.clinic import Clinic
from app.models.user import User, UserRole
from app.models.subscription import SubscriptionTier, SubscriptionPayment, SubscriptionStatus
from app.middleware.auth import platform_admin_required, get_current_user
from app.utils.seeder import create_clinic
from app.utils import storage
from app.routes.treatments import _read_upload_or_error
```

- [ ] **Step 2: Add the upload route**

Right after `update_clinic`'s closing (the line `return jsonify({"clinic": clinic.to_dict(), "message": "Clínica actualizada"}), 200`), add:

```python

@platform_bp.route("/clinics/<int:clinic_id>/logo", methods=["POST"])
@platform_admin_required
def upload_clinic_logo(clinic_id):
    """
    Subir el logo de una clínica
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    consumes:
      - multipart/form-data
    description: >
      Reemplaza el logo actual de la clínica (si existe). La imagen se guarda en
      el mismo almacenamiento privado que las fotos clínicas, en una ruta fija
      por clínica — subir un logo nuevo pisa al anterior, sin dejar huérfanos.
    parameters:
      - in: path
        name: clinic_id
        type: integer
        required: true
      - in: formData
        name: file
        type: file
        required: true
        description: Imagen JPEG, PNG o WEBP (comprimida en el cliente).
    responses:
      200:
        description: Logo actualizado
        schema:
          type: object
          properties:
            clinic:
              $ref: '#/definitions/Clinic'
            message:
              type: string
      400:
        description: Archivo inválido
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Clínica no encontrada
        schema:
          $ref: '#/definitions/Error'
      503:
        description: Almacenamiento no configurado
        schema:
          $ref: '#/definitions/Error'
    """
    clinic = Clinic.query.get_or_404(clinic_id, description="Clínica no encontrada")

    result, error = _read_upload_or_error()
    if error:
        return error
    data, content_type = result

    storage_path = f"clinic_{clinic.id}/logo.jpg"
    try:
        storage.upload_object(storage_path, data, content_type)
    except storage.StorageError:
        return jsonify({"error": "No se pudo subir el logo al almacenamiento"}), 502

    clinic.logo_url = storage_path
    db.session.commit()

    return jsonify({"clinic": clinic.to_dict(), "message": "Logo actualizado"}), 200
```

- [ ] **Step 3: Restart backend and verify manually**

Run: `docker compose restart backend`

Verify via Swagger UI (`http://localhost:5000/api/docs/`) or curl, authenticated as a platform admin:
1. First check storage is configured (see Global Constraints).
2. `POST /api/platform/clinics/<id>/logo` with a real small JPEG file in the `file` form field → expect `200`, response `clinic.logo_url` equals `"clinic_<id>/logo.jpg"`.
3. Upload a second, different image to the SAME clinic → expect `200` again, `logo_url` unchanged (same path — confirms overwrite behavior, not two separate objects).
4. `POST` with no file → expect `400` with the existing "No se envió ninguna imagen" message (proves `_read_upload_or_error` is genuinely wired in, not reimplemented).

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add backend/app/routes/platform_admin.py
git commit -m "feat(backend): add clinic logo upload endpoint"
```

---

### Task 2: Backend — clinic logo serving endpoints

**Files:**
- Modify: `backend/app/routes/clinic.py` (add `_serve_clinic_logo` helper + `GET /logo`)
- Modify: `backend/app/routes/platform_admin.py` (add `GET /clinics/<id>/logo`)

**Interfaces:**
- Consumes: `Clinic.logo_url` (the storage path written by Task 1), `storage.download_object(path)` / `storage.StorageError` (existing).
- Produces: `_serve_clinic_logo(clinic) -> Response | (jsonify_response, status)` — a shared helper both routes call. `GET /api/clinic/logo` (self-scoped) and `GET /api/platform/clinics/<id>/logo` (id-scoped) both return raw JPEG bytes on 200. Task 4 (`frontend/`'s `ClinicService.getLogoBlob()`) and Task 6 (`admin-frontend`'s `PlatformService.getClinicLogoBlob()`) call these exact routes.

- [ ] **Step 1: Add the shared helper and self-scoped route to `clinic.py`**

Change:
```python
from flask import Blueprint, jsonify
from app.middleware.auth import clinical_access_required, get_current_user
from app.models.clinic import Clinic

clinic_bp = Blueprint("clinic", __name__)
```
to:
```python
from flask import Blueprint, jsonify, Response
from app.middleware.auth import clinical_access_required, get_current_user
from app.models.clinic import Clinic
from app.utils import storage

clinic_bp = Blueprint("clinic", __name__)


def _serve_clinic_logo(clinic):
    """Stream a clinic's logo bytes from private storage, or a JSON error tuple.
    Shared by the self-scoped /clinic/logo route and the id-scoped
    /platform/clinics/<id>/logo route."""
    if not clinic.logo_url:
        return jsonify({"error": "Esta clínica no tiene logo"}), 404
    if not storage.is_configured():
        return jsonify({"error": "Almacenamiento de imágenes no configurado."}), 503
    try:
        data = storage.download_object(clinic.logo_url)
    except storage.StorageError:
        return jsonify({"error": "No se pudo recuperar el logo del almacenamiento"}), 502
    return Response(
        data,
        mimetype="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )
```

Then, after the existing `clinic_info()` function (its final `}), 200` line), add:
```python


@clinic_bp.route("/logo", methods=["GET"])
@clinical_access_required
def clinic_logo():
    """
    Logo de la clínica del usuario autenticado
    ---
    tags:
      - Clínica
    security:
      - BearerAuth: []
    produces:
      - image/jpeg
    responses:
      200:
        description: Bytes del logo
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Usuario sin clínica asignada, o clínica sin logo
        schema:
          $ref: '#/definitions/Error'
      503:
        description: Almacenamiento no configurado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    if not current.clinic_id:
        return jsonify({"error": "Usuario sin clínica asignada"}), 404
    clinic = Clinic.query.get_or_404(current.clinic_id, description="Clínica no encontrada")
    return _serve_clinic_logo(clinic)
```

- [ ] **Step 2: Add the id-scoped route to `platform_admin.py`**

Change:
```python
from app.utils import storage
from app.routes.treatments import _read_upload_or_error
```
to:
```python
from app.utils import storage
from app.routes.treatments import _read_upload_or_error
from app.routes.clinic import _serve_clinic_logo
```

Then, right after `upload_clinic_logo`'s closing (Task 1's new route), add:
```python


@platform_bp.route("/clinics/<int:clinic_id>/logo", methods=["GET"])
@platform_admin_required
def get_clinic_logo(clinic_id):
    """
    Logo de una clínica (vista de plataforma)
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    produces:
      - image/jpeg
    parameters:
      - in: path
        name: clinic_id
        type: integer
        required: true
    responses:
      200:
        description: Bytes del logo
      404:
        description: Clínica no encontrada, o sin logo
        schema:
          $ref: '#/definitions/Error'
      503:
        description: Almacenamiento no configurado
        schema:
          $ref: '#/definitions/Error'
    """
    clinic = Clinic.query.get_or_404(clinic_id, description="Clínica no encontrada")
    return _serve_clinic_logo(clinic)
```

- [ ] **Step 3: Restart backend and verify manually**

Run: `docker compose restart backend`

Verify via Swagger UI or curl:
1. As a platform admin, `GET /api/platform/clinics/<id>/logo` for the clinic Task 1 uploaded a logo to → expect `200` with `Content-Type: image/jpeg` and real image bytes (save the response and confirm it opens as a valid image, or at minimum confirm the byte length matches what was uploaded).
2. As a regular clinic user belonging to that same clinic, `GET /api/clinic/logo` → expect the same `200` behavior (same bytes).
3. As that same regular clinic user, `GET /api/platform/clinics/<id>/logo` → expect `403` (platform-admin-only route, unchanged gating).
4. `GET /api/clinic/logo` for a clinic with no logo uploaded yet (or as a platform-admin user, who has no `clinic_id`) → expect `404`.

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add backend/app/routes/clinic.py backend/app/routes/platform_admin.py
git commit -m "feat(backend): serve clinic logos via authenticated endpoints"
```

---

### Task 3: Backend — stop `update_clinic` from accepting `logo_url` as free text

**Files:**
- Modify: `backend/app/routes/platform_admin.py:305-306` (Swagger schema), `:349-350` (field handler)

**Interfaces:**
- Consumes: none new.
- Produces: `PUT /api/platform/clinics/<id>` no longer accepts/writes `logo_url` — prevents a stray client sending `{"logo_url": "anything"}` from corrupting the internal storage-path value Task 1's upload endpoint writes.

- [ ] **Step 1: Remove the Swagger property**

Change:
```python
            address:
              type: string
            phone:
              type: string
            logo_url:
              type: string
            plan_started_at:
```
to:
```python
            address:
              type: string
            phone:
              type: string
            plan_started_at:
```

- [ ] **Step 2: Remove the field handler**

Change:
```python
    if "phone" in data:
        clinic.phone = data["phone"]
    if "logo_url" in data:
        clinic.logo_url = data["logo_url"]
    if "subscription_tier_id" in data:
```
to:
```python
    if "phone" in data:
        clinic.phone = data["phone"]
    if "subscription_tier_id" in data:
```

- [ ] **Step 3: Restart backend and verify manually**

Run: `docker compose restart backend`

Verify: `PUT /api/platform/clinics/<id>` with `{"logo_url": "hijacked-value"}` in the body → expect `200` (the request itself still succeeds, since other fields are optional and none were invalid), but `GET /api/platform/clinics/<id>` immediately after shows `logo_url` **unchanged** from before this PUT — proving the field is now silently ignored rather than overwriting the real storage path.

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add backend/app/routes/platform_admin.py
git commit -m "fix(backend): stop update_clinic from accepting logo_url as free text"
```

---

### Task 4: Frontend (`frontend/`) — fetch and display the logo as an authenticated blob

**Files:**
- Modify: `frontend/src/app/core/services/api.service.ts:289-295` (`ClinicService`)
- Modify: `frontend/src/app/features/treatments/treatment-receta.component.ts`
- Modify: `frontend/src/app/features/treatments/treatment-receta.component.html`

**Interfaces:**
- Consumes: `GET /api/clinic/logo` (Task 2).
- Produces: `ClinicService.getLogoBlob(): Observable<Blob>`. `TreatmentRecetaComponent.logoUrl: Signal<SafeUrl | null>` — the template reads this instead of `clinic()!.logo_url` directly.

- [ ] **Step 1: Add `getLogoBlob()` to `ClinicService`**

Change:
```typescript
export class ClinicService {
  constructor(private http: HttpClient) {}

  getInfo(): Observable<ClinicInfo> {
    return this.http.get<ClinicInfo>(`${API}/clinic/info`);
  }
}
```
to:
```typescript
export class ClinicService {
  constructor(private http: HttpClient) {}

  getInfo(): Observable<ClinicInfo> {
    return this.http.get<ClinicInfo>(`${API}/clinic/info`);
  }

  getLogoBlob(): Observable<Blob> {
    return this.http.get(`${API}/clinic/logo`, { responseType: 'blob' });
  }
}
```

- [ ] **Step 2: Fetch the logo as a blob in `TreatmentRecetaComponent`**

Change:
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
to:
```typescript
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
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
export class TreatmentRecetaComponent implements OnInit, OnDestroy {
  loading = signal(true);
  error = signal('');
  treatment = signal<Treatment | null>(null);
  patient = signal<Patient | null>(null);
  clinic = signal<ClinicInfo | null>(null);
  doctorSpecialty = signal('');
  logoUrl = signal<SafeUrl | null>(null);

  private logoObjectUrl: string | null = null;

  constructor(
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    private patientService: PatientService,
    private userService: UserService,
    private clinicService: ClinicService,
    private sanitizer: DomSanitizer,
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
            if (clinic.logo_url) this.loadLogo();
          },
          error: () => { this.error.set('No se pudo cargar la información de la receta'); this.loading.set(false); },
        });
      },
      error: () => { this.error.set('Atención no encontrada'); this.loading.set(false); },
    });
  }

  ngOnDestroy(): void {
    if (this.logoObjectUrl) URL.revokeObjectURL(this.logoObjectUrl);
  }

  private loadLogo(): void {
    this.clinicService.getLogoBlob().subscribe({
      next: blob => {
        this.logoObjectUrl = URL.createObjectURL(blob);
        this.logoUrl.set(this.sanitizer.bypassSecurityTrustUrl(this.logoObjectUrl));
      },
      error: () => {},
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

- [ ] **Step 3: Bind the template to the fetched blob URL**

Change:
```html
      @if (clinic()!.logo_url) {
        <img [src]="clinic()!.logo_url" alt="Logo" class="clinic-logo"/>
      }
```
to:
```html
      @if (logoUrl()) {
        <img [src]="logoUrl()" alt="Logo" class="clinic-logo"/>
      }
```

- [ ] **Step 4: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints, log in as `admin@clinica.com`, navigate to a treatment's `/receta` page for a clinic that has a logo uploaded (from Task 1's verification). Confirm the `<img>` element's `src` attribute is a `blob:` URL (not the raw `clinic_3/logo.jpg` string), and that it actually renders a visible image (check `naturalWidth > 0` via `page.evaluate`, or take a screenshot). Also confirm a clinic with NO logo shows no `<img class="clinic-logo">` element at all.

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/core/services/api.service.ts frontend/src/app/features/treatments/treatment-receta.component.ts frontend/src/app/features/treatments/treatment-receta.component.html
git commit -m "feat(frontend): fetch clinic logo as authenticated blob in receta view"
```

---

### Task 5: `admin-frontend` — port the image-compression utility

**Files:**
- Create: `admin-frontend/src/app/shared/utils/image-compression.ts`

**Interfaces:**
- Produces: `compressImage(file: File, maxDim?: number, quality?: number): Promise<{blob: Blob, filename: string}>` — identical signature/behavior to `frontend/src/app/shared/utils/image-compression.ts`. Task 7 calls this with `compressImage(file, 400, 0.85)`.

- [ ] **Step 1: Create the ported file**

Create `admin-frontend/src/app/shared/utils/image-compression.ts` with this exact content (a literal copy of the already-working, already-reviewed `frontend/src/app/shared/utils/image-compression.ts` — no logic changes, `admin-frontend` is a separate Angular app/codebase and cannot import across app boundaries):

```typescript
/**
 * Client-side image compression.
 *
 * Photos are downscaled and re-encoded as JPEG in the browser *before* upload,
 * so the backend/storage only ever receives small files (~150-400KB) — no
 * server-side image library needed. See FCLI-10.
 */

export interface CompressResult {
  blob: Blob;
  filename: string;
}

const DEFAULT_MAX_DIM = 1600;   // px, longest side
const DEFAULT_QUALITY = 0.7;    // JPEG quality 0..1

/**
 * Load `file` into an image, scale it so its longest side is at most `maxDim`,
 * and re-encode as JPEG. Returns the compressed Blob plus a `.jpg` filename.
 */
export function compressImage(
  file: File,
  maxDim: number = DEFAULT_MAX_DIM,
  quality: number = DEFAULT_QUALITY,
): Promise<CompressResult> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const img = new Image();

    img.onload = () => {
      URL.revokeObjectURL(objectUrl);

      let { width, height } = img;
      if (width > maxDim || height > maxDim) {
        const scale = Math.min(maxDim / width, maxDim / height);
        width = Math.round(width * scale);
        height = Math.round(height * scale);
      }

      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('No se pudo procesar la imagen'));
        return;
      }
      ctx.drawImage(img, 0, 0, width, height);

      canvas.toBlob(
        blob => {
          if (!blob) {
            reject(new Error('No se pudo comprimir la imagen'));
            return;
          }
          const base = (file.name.replace(/\.[^.]+$/, '') || 'foto');
          resolve({ blob, filename: `${base}.jpg` });
        },
        'image/jpeg',
        quality,
      );
    };

    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error('Archivo de imagen inválido'));
    };

    img.src = objectUrl;
  });
}
```

- [ ] **Step 2: Verify the admin-frontend still compiles**

Run: `docker compose exec admin-frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json`
Expected: no errors (this is a new, self-contained, unimported file — it can't break anything by existing; this check just confirms it's syntactically valid TypeScript in this project's config).

- [ ] **Step 3: Commit**

Ask the user before running this.

```bash
git add admin-frontend/src/app/shared/utils/image-compression.ts
git commit -m "feat(admin-frontend): port client-side image compression utility"
```

---

### Task 6: `admin-frontend` — `PlatformService` logo upload/fetch methods

**Files:**
- Modify: `admin-frontend/src/app/core/services/platform.service.ts:36-43` (insert after `updateClinic`)

**Interfaces:**
- Consumes: `POST /api/platform/clinics/<id>/logo`, `GET /api/platform/clinics/<id>/logo` (Task 1/2).
- Produces: `PlatformService.uploadClinicLogo(clinicId: number, blob: Blob, filename: string): Observable<{clinic: Clinic, message: string}>`, `PlatformService.getClinicLogoBlob(clinicId: number): Observable<Blob>`. Task 7 calls both by these exact names.

- [ ] **Step 1: Add the two methods**

Change:
```typescript
  updateClinic(id: number, data: Partial<{
    name: string; is_active: boolean; subscription_tier_id: number | null;
    subscription_status: string; notes: string;
    plan_started_at: string | null; plan_expires_at: string | null;
    address: string | null; phone: string | null; logo_url: string | null;
  }>): Observable<{ clinic: Clinic; message: string }> {
    return this.http.put<{ clinic: Clinic; message: string }>(`${this.API}/clinics/${id}`, data);
  }

  resetAdminPassword(clinicId: number, userId?: number): Observable<{
```
to:
```typescript
  updateClinic(id: number, data: Partial<{
    name: string; is_active: boolean; subscription_tier_id: number | null;
    subscription_status: string; notes: string;
    plan_started_at: string | null; plan_expires_at: string | null;
    address: string | null; phone: string | null; logo_url: string | null;
  }>): Observable<{ clinic: Clinic; message: string }> {
    return this.http.put<{ clinic: Clinic; message: string }>(`${this.API}/clinics/${id}`, data);
  }

  uploadClinicLogo(clinicId: number, blob: Blob, filename: string): Observable<{ clinic: Clinic; message: string }> {
    const form = new FormData();
    form.append('file', blob, filename);
    return this.http.post<{ clinic: Clinic; message: string }>(`${this.API}/clinics/${clinicId}/logo`, form);
  }

  getClinicLogoBlob(clinicId: number): Observable<Blob> {
    return this.http.get(`${this.API}/clinics/${clinicId}/logo`, { responseType: 'blob' });
  }

  resetAdminPassword(clinicId: number, userId?: number): Observable<{
```

(The `updateClinic` payload type still lists `logo_url: string | null` from Task 11 of the previous plan — leave it as-is; it's harmless dead typing since Task 3 of *this* plan already made the backend ignore that field if sent, and removing it isn't necessary for this feature to work correctly.)

- [ ] **Step 2: Verify the admin-frontend still compiles**

Run: `docker compose exec admin-frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

- [ ] **Step 3: Commit**

Ask the user before running this.

```bash
git add admin-frontend/src/app/core/services/platform.service.ts
git commit -m "feat(admin-frontend): add clinic logo upload/fetch methods to PlatformService"
```

---

### Task 7: `admin-frontend` — logo upload UI in `clinic-detail.component`

**Files:**
- Modify: `admin-frontend/src/app/features/clinics/clinic-detail.component.ts`
- Modify: `admin-frontend/src/app/features/clinics/clinic-detail.component.html`
- Modify: `admin-frontend/src/app/features/clinics/clinic-detail.component.css`

**Interfaces:**
- Consumes: `compressImage()` (Task 5), `PlatformService.uploadClinicLogo()` / `.getClinicLogoBlob()` (Task 6).
- Produces: view-mode and edit-mode logo preview + a working upload flow. No new public interface — this is the final consumer in the chain.

- [ ] **Step 1: Update the component class**

Change:
```typescript
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { PlatformService } from '../../core/services/platform.service';
import { Clinic, ClinicDetail, PlatformUser, SubscriptionTier } from '../../core/models';

@Component({
  selector: 'app-clinic-detail',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './clinic-detail.component.html',
  styleUrl: './clinic-detail.component.css',
})
export class ClinicDetailComponent implements OnInit {
  clinicId!: number;
  detail = signal<ClinicDetail | null>(null);
  tiers = signal<SubscriptionTier[]>([]);
  loading = signal(true);

  editMode = signal(false);
  editForm = {
    name: '', is_active: true, subscription_tier_id: null as number | null, subscription_status: '',
    plan_started_at: '', plan_expires_at: '', notes: '',
    address: '', phone: '', logo_url: '',
  };
  savingEdit = signal(false);
  editMessage = signal('');

  paymentForm = { amount: null as number | null, payment_date: '', period_start: '', period_end: '', notes: '' };
  savingPayment = signal(false);
  paymentError = signal('');

  resetUserId: number | null = null;
  resettingPassword = signal(false);
  resetResult = signal<{ user: PlatformUser; temporary_password: string } | null>(null);
  resetError = signal('');

  constructor(private route: ActivatedRoute, private platform: PlatformService) {}

  ngOnInit(): void {
    this.clinicId = Number(this.route.snapshot.paramMap.get('id'));
    this.platform.getTiers().subscribe({ next: (r) => this.tiers.set(r.tiers) });
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.platform.getClinic(this.clinicId).subscribe({
      next: (d) => {
        this.detail.set(d);
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
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
```
to:
```typescript
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';
import { PlatformService } from '../../core/services/platform.service';
import { Clinic, ClinicDetail, PlatformUser, SubscriptionTier } from '../../core/models';
import { compressImage } from '../../shared/utils/image-compression';

@Component({
  selector: 'app-clinic-detail',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './clinic-detail.component.html',
  styleUrl: './clinic-detail.component.css',
})
export class ClinicDetailComponent implements OnInit, OnDestroy {
  clinicId!: number;
  detail = signal<ClinicDetail | null>(null);
  tiers = signal<SubscriptionTier[]>([]);
  loading = signal(true);

  editMode = signal(false);
  editForm = {
    name: '', is_active: true, subscription_tier_id: null as number | null, subscription_status: '',
    plan_started_at: '', plan_expires_at: '', notes: '',
    address: '', phone: '',
  };
  savingEdit = signal(false);
  editMessage = signal('');

  logoPreviewUrl = signal<SafeUrl | null>(null);
  uploadingLogo = signal(false);
  logoError = signal('');
  private logoObjectUrl: string | null = null;

  paymentForm = { amount: null as number | null, payment_date: '', period_start: '', period_end: '', notes: '' };
  savingPayment = signal(false);
  paymentError = signal('');

  resetUserId: number | null = null;
  resettingPassword = signal(false);
  resetResult = signal<{ user: PlatformUser; temporary_password: string } | null>(null);
  resetError = signal('');

  constructor(private route: ActivatedRoute, private platform: PlatformService, private sanitizer: DomSanitizer) {}

  ngOnInit(): void {
    this.clinicId = Number(this.route.snapshot.paramMap.get('id'));
    this.platform.getTiers().subscribe({ next: (r) => this.tiers.set(r.tiers) });
    this.load();
  }

  ngOnDestroy(): void {
    this.revokeLogoUrl();
  }

  load(): void {
    this.loading.set(true);
    this.platform.getClinic(this.clinicId).subscribe({
      next: (d) => {
        this.detail.set(d);
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
        };
        this.loading.set(false);
        this.loadLogoPreview(d.clinic.logo_url);
      },
      error: () => this.loading.set(false),
    });
  }

  private loadLogoPreview(logoUrl: string | null): void {
    this.revokeLogoUrl();
    this.logoPreviewUrl.set(null);
    if (!logoUrl) return;
    this.platform.getClinicLogoBlob(this.clinicId).subscribe({
      next: blob => {
        this.logoObjectUrl = URL.createObjectURL(blob);
        this.logoPreviewUrl.set(this.sanitizer.bypassSecurityTrustUrl(this.logoObjectUrl));
      },
      error: () => {},
    });
  }

  private revokeLogoUrl(): void {
    if (this.logoObjectUrl) {
      URL.revokeObjectURL(this.logoObjectUrl);
      this.logoObjectUrl = null;
    }
  }

  async onLogoSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    input.value = '';

    this.uploadingLogo.set(true);
    this.logoError.set('');
    try {
      const { blob, filename } = await compressImage(file, 400, 0.85);
      await firstValueFrom(this.platform.uploadClinicLogo(this.clinicId, blob, filename));
      this.uploadingLogo.set(false);
      this.load();
    } catch {
      this.uploadingLogo.set(false);
      this.logoError.set('No se pudo subir el logo');
    }
  }
```

- [ ] **Step 2: Remove `logo_url` from `saveEdit()`'s implicit payload — no code change needed, just confirm**

`saveEdit()` (unchanged, still spreads `...this.editForm`) now sends a payload with no `logo_url` key at all, since Step 1 removed it from `editForm`'s declaration and `load()`'s assignment. This is correct and requires no further edit — Task 3's backend change means it would have been ignored anyway, but this keeps the request body honest.

- [ ] **Step 3: Replace the view-mode and edit-mode logo fields in the template**

Change:
```html
        <div class="form-group">
          <label>Logo (URL)</label>
          <p>{{ detail()!.clinic.logo_url || '—' }}</p>
        </div>
```
to:
```html
        <div class="form-group">
          <label>Logo</label>
          @if (logoPreviewUrl()) {
            <img [src]="logoPreviewUrl()" alt="Logo" class="clinic-logo-preview"/>
          } @else {
            <p class="text-muted">Sin logo</p>
          }
        </div>
```

Change:
```html
          <div class="form-group">
            <label>Logo (URL de la imagen)</label>
            <input type="text" name="logo_url" [(ngModel)]="editForm.logo_url" placeholder="https://..." />
          </div>
```
to:
```html
          <div class="form-group">
            <label>Logo</label>
            @if (logoPreviewUrl()) {
              <img [src]="logoPreviewUrl()" alt="Logo" class="clinic-logo-preview"/>
            }
            <input type="file" accept="image/*" (change)="onLogoSelected($event)" [disabled]="uploadingLogo()" />
            @if (uploadingLogo()) { <small class="text-muted">Subiendo...</small> }
            @if (logoError()) { <small class="text-danger">{{ logoError() }}</small> }
          </div>
```

- [ ] **Step 4: Add the preview thumbnail CSS**

In `admin-frontend/src/app/features/clinics/clinic-detail.component.css`, add:
```css
.clinic-logo-preview { max-height: 64px; max-width: 160px; object-fit: contain; margin-bottom: 8px; display: block; }
```

- [ ] **Step 5: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints, log in to `admin-frontend` (port 4300) as a platform admin and:
1. Open a clinic's detail page, click "Editar". Select a real image file for the logo `<input type="file">`. Confirm the upload happens immediately (no need to click "Guardar cambios"), a preview `<img>` appears afterward, and its `src` is a `blob:` URL.
2. Reload the page (full navigation). Confirm the logo preview still renders in BOTH view mode and edit mode — proving it's re-fetched from the backend via `getClinicLogoBlob`, not held in memory.
3. Upload a second, different logo to the same clinic. Confirm the preview updates to the new image (not stacked/duplicated).
4. From `frontend/` (port 4200), open `/treatments/<id>/receta` for a patient belonging to that same clinic (Task 4's verification target) — confirm the SAME logo now appears in the print header, closing the loop between the two apps.

- [ ] **Step 6: Commit**

Ask the user before running this.

```bash
git add admin-frontend/src/app/features/clinics/clinic-detail.component.ts admin-frontend/src/app/features/clinics/clinic-detail.component.html admin-frontend/src/app/features/clinics/clinic-detail.component.css
git commit -m "feat(admin-frontend): upload and preview clinic logo in clinic-detail"
```
