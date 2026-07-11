# Impresión de Historia Médica del Paciente (FCLI-15) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a printable "Historia Médica" document for a patient (personal info, antecedentes médicos, odontograma estático, historial de atenciones, firmas), reusing the print-layout pattern already built for the recetario (FCLI-11), extracted into shared pieces so the two documents can't diverge.

**Architecture:** Pure frontend (`frontend/`), no backend/model changes (all data already exists: `Patient`, `medical_history`/`odontogram` JSON columns, `Treatment`, `Clinic` via the existing `GET /api/clinic/info`). Extracts the recetario's header markup into a reusable `PrintClinicHeaderComponent` and its base `@page`/`@media print` CSS into a shared stylesheet; extracts the interactive odontogram's color/FDI-numbering constants into a standalone data module so a new read-only `OdontogramPrintComponent` (plain SVG, no click handlers) can't visually diverge from the editable one. A new top-level (outside the `LayoutComponent` shell, so `@media print` doesn't print the app chrome) `PatientMedicalHistoryPrintComponent` fetches patient + odontogram + atenciones + clinic data and assembles the document, reusing the existing `<app-medical-history readonly>` component as-is. A print button is added to the patient's "Historia Médica" tab.

**Tech Stack:** Angular 18 standalone components + signals (`frontend/`). No test framework (see Global Constraints).

## Global Constraints

- **No automated test suite exists in `frontend/`** (no Karma/Jasmine spec files — confirmed in `CLAUDE.md`). Every task's verification step is a **manual check you actually perform and observe**: a TypeScript compile check, plus a live Puppeteer session against the running Docker `frontend` container. **Do not submit source-code review, a build/compile check alone, or "should work" as verification for anything touching a template — those are not verification.**
- **Live browser verification pattern:** the `frontend` Docker container is already running. Install Puppeteer once per session if not already present: `docker compose exec frontend sh -c "apk add --no-cache chromium && npm install --no-save puppeteer-core"`, then launch with `puppeteer.launch({ executablePath: '/usr/bin/chromium-browser', headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox', '--host-resolver-rules=MAP localhost:5000 backend:5000'] })`. Log in with existing seeded credentials — do not reseed/wipe the shared dev DB (it's the shared `testing` Supabase project, per `CLAUDE.md`). `window.ng.getComponent(domElement)` is useful to inspect a routed print component's signals directly (`loading()`, `error()`, `patient()`, etc.) since these pages have almost no interactive controls to click through. Delete any stray script/screenshot files you create before finishing (`git status --short` must show only your intended diff).
- Frontend code changes are picked up live by `ng serve`'s dev server inside the `frontend` container — no restart needed, unlike the backend.
- All UI strings are in Spanish, matching the existing app.
- Reuse the existing visual style (colors, fonts, spacing) from `treatment-receta.component.css` and `odontogram.component.css` — this feature is explicitly about *not* inventing a new visual language, see Tasks 1-4.
- Never `git commit`/`git push` without the user's explicit go-ahead for that specific commit — each task below ends with a commit step; pause and confirm with the user before running it rather than running it automatically.
- **Deviation from the design doc, decided during planning — `PrintClinicHeaderComponent`'s `documentTitle`/`issuedDate` inputs are optional**, rendered only when passed (`@if`). The design doc's example (`[documentTitle]="'HISTORIA MÉDICA'"`) only shows the historia-médica usage; Task 2 refactors `treatment-receta.component` to use this same header but must produce **zero visible change** (explicitly required by the design doc's own text: "Sin cambios de comportamiento visible"). Since today's recetario header has no title/date line, `treatment-receta.component.html` (Task 2) passes only `[clinic]`, and `patient-medical-history-print.component.html` (Task 6) passes all three inputs.
- **Deviation from the design doc, decided during planning — atenciones are fetched with `per_page: 200`, not `all: true`.** The design doc's table says `TreatmentService.getAll({ patient_id: id, all: true })`, but `GET /api/treatments/` (`backend/app/routes/treatments.py:34-101`) has **no `all` query parameter at all** — unlike `GET /api/appointments/`, where `all` means "show every doctor's appointments", not "disable pagination". Passing only `{ patient_id, all: true }` would silently truncate the printed atenciones list to the default `per_page=20`, which is wrong for a document whose whole purpose is a complete clinical backup. `per_page: 200` is the same override already used elsewhere in this codebase for exactly this "give me everything" need (`appointment-form.component.ts`'s availability check, documented in `CLAUDE.md`'s "Availability check architecture" note).

---

### Task 1: Shared print stylesheet + `PrintClinicHeaderComponent`

**Files:**
- Create: `frontend/src/app/shared/styles/print-document.css`
- Create: `frontend/src/app/shared/components/print-clinic-header/print-clinic-header.component.ts`
- Create: `frontend/src/app/shared/components/print-clinic-header/print-clinic-header.component.html`
- Create: `frontend/src/app/shared/components/print-clinic-header/print-clinic-header.component.css`

**Interfaces:**
- Consumes: `ClinicInfo` (`frontend/src/app/core/models/index.ts`), `ClinicService.getLogoBlob(): Observable<Blob>` (existing, `core/services/api.service.ts`).
- Produces: `.print-page` / `.error-msg` / `.print-actions` / `.no-print` CSS classes (shared stylesheet), `<app-print-clinic-header [clinic]="ClinicInfo" [documentTitle]="string?" [issuedDate]="string?">` selector `app-print-clinic-header`. Tasks 2 and 6 both consume this exact selector and these exact three input names.

- [ ] **Step 1: Create the shared print stylesheet**

Create `frontend/src/app/shared/styles/print-document.css`:

```css
.print-page { max-width: 700px; margin: 0 auto; padding: 32px; font-family: inherit; color: #1a202c; }
.error-msg { color: #c53030; font-size: 14px; }

.print-actions { margin-top: 24px; text-align: center; }
.print-actions button { padding: 10px 24px; border-radius: 8px; background: #2b6cb0; color: white; border: none; font-size: 14px; font-weight: 600; cursor: pointer; }

@media print {
  .no-print { display: none; }
  .print-page { padding: 0; }
}

@page { margin: 16mm; }
```

- [ ] **Step 2: Create `PrintClinicHeaderComponent`**

Create `frontend/src/app/shared/components/print-clinic-header/print-clinic-header.component.ts`:

```typescript
import { Component, Input, OnChanges, OnDestroy, SimpleChanges, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { ClinicService } from '../../../core/services/api.service';
import { ClinicInfo } from '../../../core/models';

/**
 * Shared header for any printable document (recetario, historia médica, ...):
 * clinic logo/name/address/phone/email, plus an optional document title and
 * issued-date line. `documentTitle`/`issuedDate` are optional and only render
 * when passed, so consumers that never had them (the recetario) look unchanged.
 */
@Component({
  selector: 'app-print-clinic-header',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './print-clinic-header.component.html',
  styleUrl: './print-clinic-header.component.css',
})
export class PrintClinicHeaderComponent implements OnChanges, OnDestroy {
  @Input() clinic!: ClinicInfo;
  @Input() documentTitle?: string;
  @Input() issuedDate?: string;

  logoUrl = signal<SafeUrl | null>(null);
  private logoObjectUrl: string | null = null;

  constructor(private clinicService: ClinicService, private sanitizer: DomSanitizer) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['clinic'] && this.clinic?.logo_url) {
      this.loadLogo();
    }
  }

  ngOnDestroy(): void {
    if (this.logoObjectUrl) URL.revokeObjectURL(this.logoObjectUrl);
  }

  private loadLogo(): void {
    if (this.logoObjectUrl) URL.revokeObjectURL(this.logoObjectUrl);
    this.clinicService.getLogoBlob().subscribe({
      next: blob => {
        this.logoObjectUrl = URL.createObjectURL(blob);
        this.logoUrl.set(this.sanitizer.bypassSecurityTrustUrl(this.logoObjectUrl));
      },
      error: () => {},
    });
  }
}
```

Create `frontend/src/app/shared/components/print-clinic-header/print-clinic-header.component.html`:

```html
<header class="print-clinic-header">
  <div class="header-side header-left">
    @if (logoUrl()) {
      <img [src]="logoUrl()" alt="Logo clínica" class="clinic-logo"/>
    }
  </div>
  <div class="clinic-info">
    <h1>{{ clinic.name }}</h1>
    @if (clinic.address) { <p>{{ clinic.address }}</p> }
    @if (clinic.phone) { <p>Tel: {{ clinic.phone }}</p> }
    @if (clinic.email) { <p>{{ clinic.email }}</p> }
    @if (documentTitle) { <p class="doc-title">{{ documentTitle }}</p> }
    @if (issuedDate) { <p class="doc-date">{{ issuedDate }}</p> }
  </div>
  <div class="header-side header-right">
    <img src="assets/mydentalsys-logo.svg" alt="My Dental Sys" class="system-logo"/>
  </div>
</header>
```

Create `frontend/src/app/shared/components/print-clinic-header/print-clinic-header.component.css`:

```css
.print-clinic-header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-bottom: 2px solid #2b6cb0; padding-bottom: 16px; margin-bottom: 20px; }
.header-side { flex: 0 0 90px; display: flex; align-items: center; }
.header-left { justify-content: flex-start; }
.header-right { justify-content: flex-end; }
.clinic-logo, .system-logo { max-height: 64px; max-width: 100%; object-fit: contain; }
.clinic-info { flex: 1; text-align: center; }
.clinic-info h1 { font-size: 18px; margin: 0 0 4px; color: #1a202c; }
.clinic-info p { font-size: 13px; color: #4a5568; margin: 0; }
.doc-title { font-size: 14px !important; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #2b6cb0 !important; margin-top: 8px !important; }
.doc-date { font-size: 12px !important; color: #718096 !important; margin-top: 2px !important; }

@media print {
  .print-clinic-header { display: flex; align-items: center; justify-content: space-between; }
  .header-side { flex: 0 0 90px; }
  .clinic-logo, .system-logo { max-height: 64px; }
}
```

- [ ] **Step 3: Verify the frontend still compiles**

Run: `docker compose exec frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json`
Expected: no new errors — these are brand-new files not yet imported anywhere, so this only confirms they're individually well-typed.

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/shared/styles/print-document.css frontend/src/app/shared/components/print-clinic-header
git commit -m "feat(frontend): add shared print stylesheet and PrintClinicHeaderComponent"
```

---

### Task 2: Refactor `treatment-receta.component` to use the shared header/stylesheet

**Files:**
- Modify: `frontend/src/app/features/treatments/treatment-receta.component.ts`
- Modify: `frontend/src/app/features/treatments/treatment-receta.component.html`
- Modify: `frontend/src/app/features/treatments/treatment-receta.component.css`

**Interfaces:**
- Consumes: `PrintClinicHeaderComponent`, `print-document.css`'s `.print-page`/`.error-msg`/`.print-actions`/`.no-print` (Task 1).
- Produces: no change to this component's own public surface (`loading`, `error`, `treatment`, `patient`, `clinic`, `doctorSpecialty`, `formatDate()`, `print()` — same names/types as before). Logo loading/sanitizing is removed from this component (now owned by `PrintClinicHeaderComponent`).

- [ ] **Step 1: Remove logo-loading logic, now owned by `PrintClinicHeaderComponent`**

In `frontend/src/app/features/treatments/treatment-receta.component.ts`, change:
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
    if (this.logoObjectUrl) URL.revokeObjectURL(this.logoObjectUrl);
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
to:
```typescript
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { TreatmentService, PatientService, UserService, ClinicService } from '../../core/services/api.service';
import { Treatment, Patient, ClinicInfo } from '../../core/models';
import { PrintClinicHeaderComponent } from '../../shared/components/print-clinic-header/print-clinic-header.component';

@Component({
  selector: 'app-treatment-receta',
  standalone: true,
  imports: [CommonModule, PrintClinicHeaderComponent],
  templateUrl: './treatment-receta.component.html',
  styleUrls: ['./treatment-receta.component.css', '../../shared/styles/print-document.css'],
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

- [ ] **Step 2: Replace the hardcoded header with `<app-print-clinic-header>`, drop the `.receta-page` wrapper class in favor of the shared `.print-page`**

In `frontend/src/app/features/treatments/treatment-receta.component.html`, change:
```html
<div class="receta-page">
  @if (loading()) {
    <p>Cargando...</p>
  } @else if (error()) {
    <p class="error-msg">{{ error() }}</p>
  } @else if (treatment() && patient() && clinic()) {
    <header class="receta-header">
      <div class="header-side header-left">
        @if (logoUrl()) {
          <img [src]="logoUrl()" alt="Logo clínica" class="clinic-logo"/>
        }
      </div>
      <div class="clinic-info">
        <h1>{{ clinic()!.name }}</h1>
        @if (clinic()!.address) { <p>{{ clinic()!.address }}</p> }
        @if (clinic()!.phone) { <p>Tel: {{ clinic()!.phone }}</p> }
        @if (clinic()!.email) { <p>{{ clinic()!.email }}</p> }
      </div>
      <div class="header-side header-right">
        <img src="assets/mydentalsys-logo.svg" alt="My Dental Sys" class="system-logo"/>
      </div>
    </header>
```
to:
```html
<div class="print-page">
  @if (loading()) {
    <p>Cargando...</p>
  } @else if (error()) {
    <p class="error-msg">{{ error() }}</p>
  } @else if (treatment() && patient() && clinic()) {
    <app-print-clinic-header [clinic]="clinic()!"></app-print-clinic-header>
```

- [ ] **Step 3: Remove the header/base CSS now owned by Task 1's shared files**

In `frontend/src/app/features/treatments/treatment-receta.component.css`, change:
```css
.receta-page { max-width: 700px; margin: 0 auto; padding: 32px; font-family: inherit; color: #1a202c; }
.error-msg { color: #c53030; font-size: 14px; }

.receta-header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-bottom: 2px solid #2b6cb0; padding-bottom: 16px; margin-bottom: 20px; }
.header-side { flex: 0 0 90px; display: flex; align-items: center; }
.header-left { justify-content: flex-start; }
.header-right { justify-content: flex-end; }
.clinic-logo, .system-logo { max-height: 64px; max-width: 100%; object-fit: contain; }
.clinic-info { flex: 1; text-align: center; }
.clinic-info h1 { font-size: 18px; margin: 0 0 4px; color: #1a202c; }
.clinic-info p { font-size: 13px; color: #4a5568; margin: 0; }

.patient-info { margin-bottom: 20px; font-size: 14px; }
.patient-info p { margin: 4px 0; }   
```
to:
```css
.patient-info { margin-bottom: 20px; font-size: 14px; }
.patient-info p { margin: 4px 0; }
```

Then change:
```css
.print-actions { margin-top: 24px; text-align: center; }
.print-actions button { padding: 10px 24px; border-radius: 8px; background: #2b6cb0; color: white; border: none; font-size: 14px; font-weight: 600; cursor: pointer; }

@media print {
  .no-print { display: none; }
  .receta-page { padding: 0; }
  .receta-header { display: flex; align-items: center; justify-content: space-between; }
  .header-side { flex: 0 0 90px; }
  .clinic-logo, .system-logo { max-height: 64px; }
}

@page { margin: 16mm; }
```
to nothing (delete this whole block — `.print-actions`/`.no-print`/`@media print .print-page`/`@page` now live in the shared `print-document.css`; the header-specific `@media print` rules now live in `print-clinic-header.component.css`).

The final `treatment-receta.component.css` should contain only: `.patient-info`, `.rx-block`, `.rx-symbol`, `.medication-item`, `.med-name`, `.med-detail`, `.med-indications`, `.notes-block`, `.signature-block`, `.signature-line`, `.doctor-name`, `.doctor-specialty` (all unchanged from before).

- [ ] **Step 4: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints, open `/treatments/<id>/receta` for a treatment that has `has_prescription: true` with medications (any such treatment already in the shared dev DB, e.g. one created during FCLI-11's own verification):
1. Confirm the page renders identically to before the refactor: clinic logo (if the clinic has one)/name/address/phone/email centered header with the blue bottom border, `MyDentalSys` logo on the right, patient info, medication list, signature block, "Imprimir" button.
2. Confirm there is **no** "RECETA" title or issued-date line in the header (this refactor must be visually silent — `documentTitle`/`issuedDate` are not passed here).
3. Confirm `window.print()` (via the "Imprimir" button, or the browser's print preview) still produces the same one-page layout as before.
4. TypeScript compile check: `docker compose exec frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json` → no errors.

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/treatments/treatment-receta.component.ts frontend/src/app/features/treatments/treatment-receta.component.html frontend/src/app/features/treatments/treatment-receta.component.css
git commit -m "refactor(frontend): extract recetario header into shared PrintClinicHeaderComponent"
```

---

### Task 3: Extract odontogram color/FDI constants to `odontogram-data.ts`

**Files:**
- Create: `frontend/src/app/features/patients/odontogram-data.ts`
- Modify: `frontend/src/app/features/patients/odontogram.component.ts`

**Interfaces:**
- Produces: `ToothData { status: string; notes: string; }`, `StatusOption { key: string; label: string; fill: string; stroke: string; }`, `STATUS_CONFIG: Record<string, {label,fill,stroke}>` (9 entries), `Q1`/`Q2`/`Q3`/`Q4: number[]` (FDI quadrant arrays), `TOOTH_NAMES: Record<number,string>`. Task 4's `OdontogramPrintComponent` imports all of these by these exact names — this must be a pure extraction with byte-identical values (no renumbering, no recoloring).

- [ ] **Step 1: Create `odontogram-data.ts` with the extracted constants**

Create `frontend/src/app/features/patients/odontogram-data.ts`:

```typescript
export interface ToothData {
  status: string;
  notes: string;
}

export interface StatusOption {
  key: string;
  label: string;
  fill: string;
  stroke: string;
}

export const STATUS_CONFIG: Record<string, { label: string; fill: string; stroke: string }> = {
  healthy:            { label: 'Sano',           fill: '#f8fafc', stroke: '#a0aec0' },
  caries:             { label: 'Caries',          fill: '#fed7d7', stroke: '#fc8181' },
  restoration:        { label: 'Restauración',    fill: '#bee3f8', stroke: '#4299e1' },
  crown:              { label: 'Corona',           fill: '#fef3c7', stroke: '#d69e2e' },
  extracted:          { label: 'Extraído',         fill: '#edf2f7', stroke: '#718096' },
  endodontics:        { label: 'Endodoncia',       fill: '#e9d8fd', stroke: '#9f7aea' },
  implant:            { label: 'Implante',         fill: '#c6f6d5', stroke: '#38a169' },
  fracture:           { label: 'Fractura',         fill: '#fde8d0', stroke: '#dd6b20' },
  missing_congenital: { label: 'Ausente',          fill: '#f7fafc', stroke: '#e2e8f0' },
};

// FDI quadrant arrays (display order: patient's right on the left)
export const Q1 = [18, 17, 16, 15, 14, 13, 12, 11]; // upper right
export const Q2 = [21, 22, 23, 24, 25, 26, 27, 28]; // upper left
export const Q4 = [48, 47, 46, 45, 44, 43, 42, 41]; // lower right
export const Q3 = [31, 32, 33, 34, 35, 36, 37, 38]; // lower left

export const TOOTH_NAMES: Record<number, string> = {
  11: 'Incisivo Central',  12: 'Incisivo Lateral', 13: 'Canino',
  14: 'Premolar 1',        15: 'Premolar 2',
  16: 'Molar 1',           17: 'Molar 2',          18: 'Cordal',
  21: 'Incisivo Central',  22: 'Incisivo Lateral', 23: 'Canino',
  24: 'Premolar 1',        25: 'Premolar 2',
  26: 'Molar 1',           27: 'Molar 2',          28: 'Cordal',
  31: 'Incisivo Central',  32: 'Incisivo Lateral', 33: 'Canino',
  34: 'Premolar 1',        35: 'Premolar 2',
  36: 'Molar 1',           37: 'Molar 2',          38: 'Cordal',
  41: 'Incisivo Central',  42: 'Incisivo Lateral', 43: 'Canino',
  44: 'Premolar 1',        45: 'Premolar 2',
  46: 'Molar 1',           47: 'Molar 2',          48: 'Cordal',
};
```

- [ ] **Step 2: Update `odontogram.component.ts` to import from the new module instead of declaring locally**

In `frontend/src/app/features/patients/odontogram.component.ts`, change:
```typescript
import { Component, Input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PatientService } from '../../core/services/api.service';

interface ToothData {
  status: string;
  notes: string;
}

interface StatusOption {
  key: string;
  label: string;
  fill: string;
  stroke: string;
}

const STATUS_CONFIG: Record<string, { label: string; fill: string; stroke: string }> = {
  healthy:            { label: 'Sano',           fill: '#f8fafc', stroke: '#a0aec0' },
  caries:             { label: 'Caries',          fill: '#fed7d7', stroke: '#fc8181' },
  restoration:        { label: 'Restauración',    fill: '#bee3f8', stroke: '#4299e1' },
  crown:              { label: 'Corona',           fill: '#fef3c7', stroke: '#d69e2e' },
  extracted:          { label: 'Extraído',         fill: '#edf2f7', stroke: '#718096' },
  endodontics:        { label: 'Endodoncia',       fill: '#e9d8fd', stroke: '#9f7aea' },
  implant:            { label: 'Implante',         fill: '#c6f6d5', stroke: '#38a169' },
  fracture:           { label: 'Fractura',         fill: '#fde8d0', stroke: '#dd6b20' },
  missing_congenital: { label: 'Ausente',          fill: '#f7fafc', stroke: '#e2e8f0' },
};
```
to:
```typescript
import { Component, Input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PatientService } from '../../core/services/api.service';
import {
  ToothData, StatusOption, STATUS_CONFIG,
  Q1 as ODONTO_Q1, Q2 as ODONTO_Q2, Q3 as ODONTO_Q3, Q4 as ODONTO_Q4,
  TOOTH_NAMES,
} from './odontogram-data';
```

Then change:
```typescript
  // FDI quadrant arrays (display order: patient's right on the left)
  readonly Q1 = [18, 17, 16, 15, 14, 13, 12, 11]; // upper right
  readonly Q2 = [21, 22, 23, 24, 25, 26, 27, 28]; // upper left
  readonly Q4 = [48, 47, 46, 45, 44, 43, 42, 41]; // lower right
  readonly Q3 = [31, 32, 33, 34, 35, 36, 37, 38]; // lower left

  readonly statuses: StatusOption[] = Object.entries(STATUS_CONFIG).map(([key, v]) => ({ key, ...v }));

  private readonly toothNames: Record<number, string> = {
    11: 'Incisivo Central',  12: 'Incisivo Lateral', 13: 'Canino',
    14: 'Premolar 1',        15: 'Premolar 2',
    16: 'Molar 1',           17: 'Molar 2',          18: 'Cordal',
    21: 'Incisivo Central',  22: 'Incisivo Lateral', 23: 'Canino',
    24: 'Premolar 1',        25: 'Premolar 2',
    26: 'Molar 1',           27: 'Molar 2',          28: 'Cordal',
    31: 'Incisivo Central',  32: 'Incisivo Lateral', 33: 'Canino',
    34: 'Premolar 1',        35: 'Premolar 2',
    36: 'Molar 1',           37: 'Molar 2',          38: 'Cordal',
    41: 'Incisivo Central',  42: 'Incisivo Lateral', 43: 'Canino',
    44: 'Premolar 1',        45: 'Premolar 2',
    46: 'Molar 1',           47: 'Molar 2',          48: 'Cordal',
  };
```
to:
```typescript
  // FDI quadrant arrays (display order: patient's right on the left) — from odontogram-data.ts
  readonly Q1 = ODONTO_Q1;
  readonly Q2 = ODONTO_Q2;
  readonly Q4 = ODONTO_Q4;
  readonly Q3 = ODONTO_Q3;

  readonly statuses: StatusOption[] = Object.entries(STATUS_CONFIG).map(([key, v]) => ({ key, ...v }));

  private readonly toothNames: Record<number, string> = TOOTH_NAMES;
```

The rest of `odontogram.component.ts` (all methods, `readonly statusConfig = STATUS_CONFIG;` at the bottom) is unchanged — `STATUS_CONFIG` and `ToothData` are now imported types/values instead of locally declared ones, with identical shape.

- [ ] **Step 3: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints, open a patient's "Odontograma" tab (any patient with odontogram data from earlier FCLI work):
1. Confirm the chart renders exactly as before: same colors, same tooth numbers/positions, same legend.
2. Click a tooth, change its status, save — confirm this still works (proves `PatientService.saveOdontogram` and the edit panel are untouched).
3. TypeScript compile check: `docker compose exec frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json` → no errors.

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/patients/odontogram-data.ts frontend/src/app/features/patients/odontogram.component.ts
git commit -m "refactor(frontend): extract odontogram color/FDI constants to odontogram-data.ts"
```

---

### Task 4: New `OdontogramPrintComponent` (static, read-only)

**Files:**
- Create: `frontend/src/app/features/patients/odontogram-print.component.ts`
- Create: `frontend/src/app/features/patients/odontogram-print.component.html`
- Create: `frontend/src/app/features/patients/odontogram-print.component.css`

**Interfaces:**
- Consumes: `ToothData`, `StatusOption`, `STATUS_CONFIG`, `Q1`/`Q2`/`Q3`/`Q4`, `TOOTH_NAMES` (Task 3, `./odontogram-data`).
- Produces: `<app-odontogram-print [odontogram]="Record<string, ToothData>">`, selector `app-odontogram-print`. Task 6 consumes this exact selector/input name. An empty/missing odontogram (`{}` or `undefined`) renders every tooth as "Sano" — same fallback the interactive component already uses.

- [ ] **Step 1: Create the component**

Create `frontend/src/app/features/patients/odontogram-print.component.ts`:

```typescript
import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ToothData, StatusOption, STATUS_CONFIG,
  Q1 as ODONTO_Q1, Q2 as ODONTO_Q2, Q3 as ODONTO_Q3, Q4 as ODONTO_Q4,
  TOOTH_NAMES,
} from './odontogram-data';

/** Presentational, read-only odontogram for printable documents: no click handlers, no edit panel, no PatientService call — the parent passes already-loaded data. */
@Component({
  selector: 'app-odontogram-print',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './odontogram-print.component.html',
  styleUrl: './odontogram-print.component.css',
})
export class OdontogramPrintComponent {
  @Input() odontogram: Record<string, ToothData> = {};

  readonly Q1 = ODONTO_Q1;
  readonly Q2 = ODONTO_Q2;
  readonly Q4 = ODONTO_Q4;
  readonly Q3 = ODONTO_Q3;
  readonly statuses: StatusOption[] = Object.entries(STATUS_CONFIG).map(([key, v]) => ({ key, ...v }));

  private getToothData(tooth: number): ToothData {
    return this.odontogram[String(tooth)] ?? { status: 'healthy', notes: '' };
  }

  getFill(tooth: number): string {
    return STATUS_CONFIG[this.getToothData(tooth).status]?.fill ?? STATUS_CONFIG['healthy'].fill;
  }

  getStroke(tooth: number): string {
    return STATUS_CONFIG[this.getToothData(tooth).status]?.stroke ?? STATUS_CONFIG['healthy'].stroke;
  }

  isExtracted(tooth: number): boolean {
    const s = this.getToothData(tooth).status;
    return s === 'extracted' || s === 'missing_congenital';
  }

  getToothName(tooth: number): string {
    return TOOTH_NAMES[tooth] ?? `Diente ${tooth}`;
  }

  getStatusLabel(tooth: number): string {
    return STATUS_CONFIG[this.getToothData(tooth).status]?.label ?? this.getToothData(tooth).status;
  }
}
```

- [ ] **Step 2: Create the template (legend + 4-quadrant grid, no click handlers/edit panel)**

Create `frontend/src/app/features/patients/odontogram-print.component.html`:

```html
<div class="odonto-print-container">
  <!-- Legend -->
  <div class="legend">
    @for (s of statuses; track s.key) {
      <div class="legend-item">
        <div class="legend-swatch" [style.background]="s.fill" [style.border-color]="s.stroke"></div>
        <span>{{ s.label }}</span>
      </div>
    }
  </div>

  <div class="chart">
    <!-- Quadrant labels (above upper jaw) -->
    <div class="quad-labels">
      <div class="quad-label q1">Cuadrante 1<br><small>Superior Derecho</small></div>
      <div class="quad-sep"></div>
      <div class="quad-label q2">Cuadrante 2<br><small>Superior Izquierdo</small></div>
    </div>

    <!-- UPPER JAW -->
    <div class="jaw upper-jaw">
      <div class="num-row">
        @for (t of Q1; track t) { <div class="num-cell">{{ t }}</div> }
        <div class="jaw-midline"></div>
        @for (t of Q2; track t) { <div class="num-cell">{{ t }}</div> }
      </div>
      <div class="tooth-row">
        @for (t of Q1; track t) {
          <div class="tooth-cell" [title]="getToothName(t) + ' — ' + getStatusLabel(t)">
            <svg viewBox="0 0 44 44" class="tooth-svg">
              <polygon points="0,0 44,0 34,10 10,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="0,44 44,44 34,34 10,34" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="0,0 0,44 10,34 10,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="44,0 44,44 34,34 34,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="10,10 34,10 34,34 10,34" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <rect x="0.5" y="0.5" width="43" height="43" rx="4" fill="none" [attr.stroke]="getStroke(t)" stroke-width="1.5"/>
              @if (isExtracted(t)) {
                <line x1="9" y1="9" x2="35" y2="35" stroke="#718096" stroke-width="2.5" stroke-linecap="round"/>
                <line x1="35" y1="9" x2="9" y2="35" stroke="#718096" stroke-width="2.5" stroke-linecap="round"/>
              }
            </svg>
          </div>
        }
        <div class="jaw-midline"></div>
        @for (t of Q2; track t) {
          <div class="tooth-cell" [title]="getToothName(t) + ' — ' + getStatusLabel(t)">
            <svg viewBox="0 0 44 44" class="tooth-svg">
              <polygon points="0,0 44,0 34,10 10,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="0,44 44,44 34,34 10,34" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="0,0 0,44 10,34 10,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="44,0 44,44 34,34 34,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="10,10 34,10 34,34 10,34" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <rect x="0.5" y="0.5" width="43" height="43" rx="4" fill="none" [attr.stroke]="getStroke(t)" stroke-width="1.5"/>
              @if (isExtracted(t)) {
                <line x1="9" y1="9" x2="35" y2="35" stroke="#718096" stroke-width="2.5" stroke-linecap="round"/>
                <line x1="35" y1="9" x2="9" y2="35" stroke="#718096" stroke-width="2.5" stroke-linecap="round"/>
              }
            </svg>
          </div>
        }
      </div>
    </div>

    <!-- Jaw divider -->
    <div class="jaw-divider">
      <div class="jaw-label-side">Maxilar Superior</div>
      <div class="divider-line"></div>
      <div class="jaw-label-side">Mandíbula Inferior</div>
    </div>

    <!-- LOWER JAW -->
    <div class="jaw lower-jaw">
      <div class="tooth-row">
        @for (t of Q4; track t) {
          <div class="tooth-cell" [title]="getToothName(t) + ' — ' + getStatusLabel(t)">
            <svg viewBox="0 0 44 44" class="tooth-svg">
              <polygon points="0,0 44,0 34,10 10,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="0,44 44,44 34,34 10,34" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="0,0 0,44 10,34 10,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="44,0 44,44 34,34 34,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="10,10 34,10 34,34 10,34" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <rect x="0.5" y="0.5" width="43" height="43" rx="4" fill="none" [attr.stroke]="getStroke(t)" stroke-width="1.5"/>
              @if (isExtracted(t)) {
                <line x1="9" y1="9" x2="35" y2="35" stroke="#718096" stroke-width="2.5" stroke-linecap="round"/>
                <line x1="35" y1="9" x2="9" y2="35" stroke="#718096" stroke-width="2.5" stroke-linecap="round"/>
              }
            </svg>
          </div>
        }
        <div class="jaw-midline"></div>
        @for (t of Q3; track t) {
          <div class="tooth-cell" [title]="getToothName(t) + ' — ' + getStatusLabel(t)">
            <svg viewBox="0 0 44 44" class="tooth-svg">
              <polygon points="0,0 44,0 34,10 10,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="0,44 44,44 34,34 10,34" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="0,0 0,44 10,34 10,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="44,0 44,44 34,34 34,10" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <polygon points="10,10 34,10 34,34 10,34" [attr.fill]="getFill(t)" [attr.stroke]="getStroke(t)" stroke-width="0.8"/>
              <rect x="0.5" y="0.5" width="43" height="43" rx="4" fill="none" [attr.stroke]="getStroke(t)" stroke-width="1.5"/>
              @if (isExtracted(t)) {
                <line x1="9" y1="9" x2="35" y2="35" stroke="#718096" stroke-width="2.5" stroke-linecap="round"/>
                <line x1="35" y1="9" x2="9" y2="35" stroke="#718096" stroke-width="2.5" stroke-linecap="round"/>
              }
            </svg>
          </div>
        }
      </div>
      <div class="num-row">
        @for (t of Q4; track t) { <div class="num-cell">{{ t }}</div> }
        <div class="jaw-midline"></div>
        @for (t of Q3; track t) { <div class="num-cell">{{ t }}</div> }
      </div>
    </div>

    <!-- Quadrant labels below lower jaw -->
    <div class="quad-labels">
      <div class="quad-label q4">Cuadrante 4<br><small>Inferior Derecho</small></div>
      <div class="quad-sep"></div>
      <div class="quad-label q3">Cuadrante 3<br><small>Inferior Izquierdo</small></div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Create the CSS (grid layout only — no hover/cursor/edit-panel/status-grid rules from the interactive component)**

Create `frontend/src/app/features/patients/odontogram-print.component.css`:

```css
.odonto-print-container { padding: 0; }

.legend {
  display: flex; flex-wrap: wrap; gap: 10px 18px;
  margin-bottom: 20px; padding: 12px 16px;
  background: #f7fafc; border-radius: 10px;
  border: 1px solid #e2e8f0;
}
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #4a5568; }
.legend-swatch { width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid; flex-shrink: 0; }

.chart { display: flex; flex-direction: column; gap: 0; min-width: 680px; }

.quad-labels { display: flex; align-items: center; padding: 6px 0; }
.quad-label { flex: 1; font-size: 11px; font-weight: 600; color: #718096; text-align: center; line-height: 1.4; }
.quad-label small { font-weight: 400; }
.quad-label.q1, .quad-label.q4 { text-align: right; padding-right: 8px; }
.quad-label.q2, .quad-label.q3 { text-align: left; padding-left: 8px; }
.quad-sep { width: 24px; flex-shrink: 0; }

.jaw { display: flex; flex-direction: column; }

.num-row { display: flex; align-items: center; }
.num-cell { width: 44px; text-align: center; font-size: 11px; font-weight: 600; color: #a0aec0; padding: 2px 0; flex-shrink: 0; }

.tooth-row { display: flex; align-items: center; }
.tooth-cell { width: 44px; height: 44px; flex-shrink: 0; }
.tooth-svg { width: 44px; height: 44px; display: block; }

.jaw-midline { width: 24px; flex-shrink: 0; display: flex; justify-content: center; }

.jaw-divider { display: flex; align-items: center; gap: 10px; margin: 4px 0; }
.jaw-label-side { font-size: 10px; color: #a0aec0; white-space: nowrap; font-weight: 500; }
.divider-line { flex: 1; height: 1px; background: #e2e8f0; }
```

- [ ] **Step 4: Verify manually in the browser (real, observed session)**

This component has no route of its own yet (Task 6 embeds it) — verify it directly via `window.ng`:
1. `docker compose exec frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json` → no errors.
2. Using Puppeteer, `page.evaluate()` a small inline test: dynamically render is not practical without a host page, so instead confirm correctness by code inspection cross-checked against `odontogram.component.html`'s SVG block (already done above — the plan's HTML is a direct copy minus click handlers/selection ring/notes dot) and defer full visual confirmation to Task 6's end-to-end verification, where this component is actually mounted on the real historia-médica page with real odontogram data (varied statuses including at least one `extracted` tooth to confirm the red X renders).

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/patients/odontogram-print.component.ts frontend/src/app/features/patients/odontogram-print.component.html frontend/src/app/features/patients/odontogram-print.component.css
git commit -m "feat(frontend): add static read-only OdontogramPrintComponent"
```

---

### Task 5: `PatientMedicalHistoryPrintComponent` — data fetching + route

**Files:**
- Create: `frontend/src/app/features/patients/patient-medical-history-print.component.ts`
- Modify: `frontend/src/app/app.routes.ts`

**Interfaces:**
- Consumes: `PatientService.getById(id)`, `PatientService.getOdontogram(id)`, `TreatmentService.getAll(params)`, `ClinicService.getInfo()` (all existing, `core/services/api.service.ts`), `AuthService.currentUser()` (existing, `core/services/auth.service.ts`), `formatDateLong()` (existing, `core/util/date.util.ts`), `ToothData` (Task 3).
- Produces: `PatientMedicalHistoryPrintComponent` with `loading: Signal<boolean>`, `error: Signal<string>`, `patient: Signal<Patient|null>`, `odontogram: Signal<Record<string,ToothData>>`, `treatments: Signal<Treatment[]>`, `clinic: Signal<ClinicInfo|null>`, `doctorName: Signal<string>`, `readonly issuedDate: string`, `formatDate(iso): string`, `print(): void`. Task 6's template reads all of these by these exact names. Route `patients/:id/historia/imprimir` registered.

- [ ] **Step 1: Create the component (data-fetching only; Task 6 adds the template)**

Create `frontend/src/app/features/patients/patient-medical-history-print.component.ts`:

```typescript
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { PatientService, TreatmentService, ClinicService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, Treatment, ClinicInfo } from '../../core/models';
import { ToothData } from './odontogram-data';
import { formatDateLong } from '../../core/util/date.util';
import { PrintClinicHeaderComponent } from '../../shared/components/print-clinic-header/print-clinic-header.component';
import { MedicalHistoryComponent } from './medical-history.component';
import { OdontogramPrintComponent } from './odontogram-print.component';

@Component({
  selector: 'app-patient-medical-history-print',
  standalone: true,
  imports: [CommonModule, PrintClinicHeaderComponent, MedicalHistoryComponent, OdontogramPrintComponent],
  templateUrl: './patient-medical-history-print.component.html',
  styleUrls: ['./patient-medical-history-print.component.css', '../../shared/styles/print-document.css'],
})
export class PatientMedicalHistoryPrintComponent implements OnInit {
  loading = signal(true);
  error = signal('');
  patient = signal<Patient | null>(null);
  odontogram = signal<Record<string, ToothData>>({});
  treatments = signal<Treatment[]>([]);
  clinic = signal<ClinicInfo | null>(null);
  doctorName = signal('');

  readonly issuedDate = formatDateLong(new Date().toISOString());

  constructor(
    private route: ActivatedRoute,
    private patientService: PatientService,
    private treatmentService: TreatmentService,
    private clinicService: ClinicService,
    private auth: AuthService,
  ) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.doctorName.set(this.auth.currentUser()?.full_name ?? '');

    forkJoin({
      patient: this.patientService.getById(id),
      odontogram: this.patientService.getOdontogram(id),
      treatments: this.treatmentService.getAll({ patient_id: id, per_page: 200 }),
      clinic: this.clinicService.getInfo(),
    }).subscribe({
      next: ({ patient, odontogram, treatments, clinic }) => {
        this.patient.set(patient.patient);
        this.odontogram.set((odontogram as Record<string, ToothData>) || {});
        this.treatments.set(
          [...(treatments.treatments as Treatment[])].sort(
            (a, b) => new Date(b.performed_at).getTime() - new Date(a.performed_at).getTime()
          )
        );
        this.clinic.set(clinic);
        this.loading.set(false);
      },
      error: () => { this.error.set('No se pudo cargar la historia médica'); this.loading.set(false); },
    });
  }

  formatDate(iso: string): string {
    return formatDateLong(iso);
  }

  print(): void {
    window.print();
  }
}
```

Note: `formatDateLong` matches the recetario's existing inline `formatDate` (`day: '2-digit', month: 'long', year: 'numeric'`) — reused from `core/util/date.util.ts` instead of duplicated, per its documented convention for instant/date-with-time fields (`Treatment.performed_at`).

- [ ] **Step 2: Create a placeholder template so the component compiles (Task 6 replaces this)**

Create `frontend/src/app/features/patients/patient-medical-history-print.component.html`:

```html
<div class="print-page">placeholder — replaced in Task 6</div>
```

Create `frontend/src/app/features/patients/patient-medical-history-print.component.css`:

```css
```

- [ ] **Step 3: Register the route**

In `frontend/src/app/app.routes.ts`, change:
```typescript
  {
    path: 'treatments/:id/receta',
    loadComponent: () =>
      import('./features/treatments/treatment-receta.component').then(m => m.TreatmentRecetaComponent),
    canActivate: [roleGuard],
    data: { pageKey: 'treatments' },
  },
  {
    path: '',
```
to:
```typescript
  {
    path: 'treatments/:id/receta',
    loadComponent: () =>
      import('./features/treatments/treatment-receta.component').then(m => m.TreatmentRecetaComponent),
    canActivate: [roleGuard],
    data: { pageKey: 'treatments' },
  },
  {
    path: 'patients/:id/historia/imprimir',
    loadComponent: () =>
      import('./features/patients/patient-medical-history-print.component').then(m => m.PatientMedicalHistoryPrintComponent),
    canActivate: [roleGuard],
    data: { pageKey: 'patients' },
  },
  {
    path: '',
```

This route sits outside the `LayoutComponent` shell (same as `treatments/:id/receta`) so `@media print` doesn't print the sidebar/header — see the design doc's "Ruta" section and the existing `35d765d` precedent referenced there.

- [ ] **Step 4: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints, navigate to `/patients/<id>/historia/imprimir` for a patient that has odontogram data, medical_history data, and at least 2 atenciones:
1. Confirm the page loads without a console error and shows the placeholder text (proves the route resolves and the component's `ngOnInit` ran without throwing).
2. `window.ng.getComponent(document.querySelector('app-patient-medical-history-print'))` and inspect: `component.loading()` is `false`, `component.patient()` is a `Patient` object matching the URL's `:id`, `component.odontogram()` is a non-empty object, `component.treatments().length >= 2` and the first entry's `performed_at` is the most recent (descending order), `component.clinic()` has a `name`, `component.doctorName()` matches the logged-in user's `full_name`, `component.issuedDate` is a non-empty formatted date string.
3. TypeScript compile check: `docker compose exec frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json` → no errors.

- [ ] **Step 5: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/patients/patient-medical-history-print.component.ts frontend/src/app/features/patients/patient-medical-history-print.component.html frontend/src/app/features/patients/patient-medical-history-print.component.css frontend/src/app/app.routes.ts
git commit -m "feat(frontend): add PatientMedicalHistoryPrintComponent data fetching and route"
```

---

### Task 6: `PatientMedicalHistoryPrintComponent` — full template

**Files:**
- Modify: `frontend/src/app/features/patients/patient-medical-history-print.component.html`
- Modify: `frontend/src/app/features/patients/patient-medical-history-print.component.css`

**Interfaces:**
- Consumes: `loading`, `error`, `patient`, `odontogram`, `treatments`, `clinic`, `doctorName`, `issuedDate`, `formatDate()`, `print()` (Task 5, exact names); `<app-print-clinic-header>` (Task 1); `<app-medical-history [value] [readonly]>` (existing `medical-history.component.ts`); `<app-odontogram-print [odontogram]>` (Task 4); `Patient.age/phone/address/city/phone_emergency/email/blood_type/allergies/document_number/full_name/medical_history`, `Treatment.performed_at/procedure/tooth_number/diagnosis/doctor_name` (existing, `core/models/index.ts`).

- [ ] **Step 1: Replace the placeholder template with the full document**

Replace the entire contents of `frontend/src/app/features/patients/patient-medical-history-print.component.html` with:

```html
<div class="print-page historia-page">
  @if (loading()) {
    <p>Cargando...</p>
  } @else if (error()) {
    <p class="error-msg">{{ error() }}</p>
  } @else if (patient() && clinic()) {
    <app-print-clinic-header
      [clinic]="clinic()!"
      documentTitle="HISTORIA MÉDICA"
      [issuedDate]="issuedDate">
    </app-print-clinic-header>

    <section class="patient-info">
      <p><strong>Paciente:</strong> {{ patient()!.full_name }}</p>
      <p><strong>C.I.:</strong> {{ patient()!.document_number }}</p>
      @if (patient()!.age !== undefined && patient()!.age !== null) {
        <p><strong>Edad:</strong> {{ patient()!.age }} años</p>
      }
      @if (patient()!.phone) {
        <p><strong>Teléfono:</strong> {{ patient()!.phone }}</p>
      }
      @if (patient()!.address) {
        <p><strong>Dirección:</strong> {{ patient()!.address }}</p>
      }
      @if (patient()!.city) {
        <p><strong>Ciudad:</strong> {{ patient()!.city }}</p>
      }
      @if (patient()!.phone_emergency) {
        <p><strong>Teléfono de emergencia:</strong> {{ patient()!.phone_emergency }}</p>
      }
      @if (patient()!.email) {
        <p><strong>Correo:</strong> {{ patient()!.email }}</p>
      }
      @if (patient()!.blood_type && patient()!.blood_type !== 'unknown') {
        <p><strong>Tipo de sangre:</strong> {{ patient()!.blood_type }}</p>
      }
      @if (patient()!.allergies) {
        <p class="allergies-row"><strong>Alergias:</strong> {{ patient()!.allergies }}</p>
      }
    </section>

    <section class="hist-section">
      <h3>Historia Médica</h3>
      <app-medical-history [value]="patient()!.medical_history" [readonly]="true"></app-medical-history>
    </section>

    <section class="odonto-section">
      <h3>Odontograma</h3>
      <app-odontogram-print [odontogram]="odontogram()"></app-odontogram-print>
    </section>

    <section class="treatments-section">
      <h3>Atenciones</h3>
      @if (treatments().length === 0) {
        <p class="empty-row">Sin atenciones registradas</p>
      } @else {
        <table class="treatments-table">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Procedimiento</th>
              <th>Pieza</th>
              <th>Diagnóstico</th>
              <th>Médico</th>
            </tr>
          </thead>
          <tbody>
            @for (t of treatments(); track t.id) {
              <tr>
                <td>{{ formatDate(t.performed_at) }}</td>
                <td>{{ t.procedure }}</td>
                <td>{{ t.tooth_number || '—' }}</td>
                <td>{{ t.diagnosis || '—' }}</td>
                <td>{{ t.doctor_name }}</td>
              </tr>
            }
          </tbody>
        </table>
      }
    </section>

    <footer class="signatures-footer">
      <div class="signature-block">
        <div class="signature-line"></div>
        <p class="signature-label">{{ patient()!.full_name }}</p>
        <p class="signature-role">Paciente</p>
      </div>
      <div class="signature-block">
        <div class="signature-line"></div>
        <p class="signature-label">{{ doctorName() }}</p>
        <p class="signature-role">Médico</p>
      </div>
    </footer>

    <div class="print-actions no-print">
      <button type="button" (click)="print()">Imprimir</button>
    </div>
  }
</div>
```

- [ ] **Step 2: Add the CSS**

Replace the entire contents of `frontend/src/app/features/patients/patient-medical-history-print.component.css` with:

```css
.historia-page { max-width: 900px; }

.patient-info { margin-bottom: 24px; font-size: 14px; }
.patient-info p { margin: 4px 0; }
.allergies-row { color: #c53030; font-weight: 600; }

.hist-section, .odonto-section, .treatments-section { margin-bottom: 28px; }
.hist-section h3, .odonto-section h3, .treatments-section h3 {
  font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em;
  color: #718096; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin: 0 0 12px;
}

.empty-row { font-size: 13px; color: #a0aec0; font-style: italic; }

.treatments-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.treatments-table th, .treatments-table td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }
.treatments-table th { font-size: 11px; text-transform: uppercase; color: #718096; font-weight: 600; }

.signatures-footer { display: flex; justify-content: space-between; gap: 40px; margin-top: 80px; }
.signature-block { flex: 1; text-align: center; }
.signature-line { border-top: 1px solid #1a202c; margin-bottom: 6px; }
.signature-label { font-size: 14px; font-weight: 600; margin: 0; }
.signature-role { font-size: 12px; color: #4a5568; margin: 2px 0 0; }

@media print {
  .treatments-table tr { page-break-inside: avoid; }
}
```

- [ ] **Step 3: Verify manually in the browser — all three scenarios from the design doc's "Verificación" section (real, observed session)**

Using the Puppeteer pattern from Global Constraints, navigate to `/patients/<id>/historia/imprimir` and extract actual rendered DOM text (not a prediction) for each scenario:

1. **Paciente con datos completos** (antecedentes registrados, odontograma con al menos un diente `caries`/`crown`/`extracted` each, 2+ atenciones): confirm the header shows "HISTORIA MÉDICA" + the current date; all populated personal-info fields render with their labels; the odontogram legend + grid render with the correct fill colors per tooth and a red X on the extracted tooth; the atenciones table lists all rows sorted most-recent-first; both signature lines show the patient's and the logged-in doctor's names.
2. **Paciente con datos parciales** (a patient with `address`/`city`/`phone_emergency`/`email` empty in the DB — or a fresh one created via the authenticated API for this check, cleaned up after): confirm those specific `<p>` rows are entirely absent from the DOM (not present-but-empty) while populated fields (name, C.I.) still show.
3. **Paciente sin antecedentes / sin odontograma / sin atenciones**: confirm `<app-medical-history>` shows "Sin antecedentes médicos registrados", the odontogram grid renders fully in "Sano" (default gray/`#f8fafc`) fill for every tooth, and the atenciones section shows "Sin atenciones registradas" — no console errors in any case.
4. **Print preview**: trigger `window.print()` (via the "Imprimir" button or Puppeteer's `page.pdf()`/print-preview equivalent) and confirm the `.no-print` button is hidden and the document lays out legibly across however many pages it needs (this document, unlike the recetario, does not need to fit one page).
5. TypeScript compile check: `docker compose exec frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json` → no errors.

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/patients/patient-medical-history-print.component.html frontend/src/app/features/patients/patient-medical-history-print.component.css
git commit -m "feat(frontend): render full historia médica printable document"
```

---

### Task 7: Integration — "Imprimir" button on the patient's Historia Médica tab

**Files:**
- Modify: `frontend/src/app/features/patients/patient-detail.component.ts`
- Modify: `frontend/src/app/features/patients/patient-detail.component.html`

**Interfaces:**
- Consumes: route `patients/:id/historia/imprimir` (Task 5), `patient: Signal<Patient|null>` (existing).
- Produces: `printMedicalHistory(): void` — opens the print route in a new tab. Same pattern as `treatment-detail.component.ts`'s existing `printReceta()`.

- [ ] **Step 1: Add `printMedicalHistory()`**

In `frontend/src/app/features/patients/patient-detail.component.ts`, change:
```typescript
  initials(p: Patient): string { return `${p.first_name[0]}${p.last_name[0]}`.toUpperCase(); }
  formatDate(iso: string): string { return fmtDate(iso); }
  formatDateTime(iso: string): string { return fmtDateTime(iso); }
```
to:
```typescript
  initials(p: Patient): string { return `${p.first_name[0]}${p.last_name[0]}`.toUpperCase(); }
  formatDate(iso: string): string { return fmtDate(iso); }
  formatDateTime(iso: string): string { return fmtDateTime(iso); }

  printMedicalHistory(): void {
    window.open(`/patients/${this.patient()!.id}/historia/imprimir`, '_blank');
  }
```

- [ ] **Step 2: Add the header + button above `<app-medical-history>` on the "notes" tab**

In `frontend/src/app/features/patients/patient-detail.component.html`, change:
```html
        @if (activeTab() === 'notes') {
          <app-medical-history [value]="patient()!.medical_history" [readonly]="true"></app-medical-history>

          <div class="tab-section-header notes-header">
            <span class="tab-section-title">Notas médicas generales</span>
          </div>
```
to:
```html
        @if (activeTab() === 'notes') {
          <div class="tab-section-header">
            <span class="tab-section-title">Historia Médica</span>
            <button type="button" class="btn btn-secondary btn-sm" (click)="printMedicalHistory()">🖨️ Imprimir</button>
          </div>
          <app-medical-history [value]="patient()!.medical_history" [readonly]="true"></app-medical-history>

          <div class="tab-section-header notes-header">
            <span class="tab-section-title">Notas médicas generales</span>
          </div>
```

No CSS changes needed — `.tab-section-header`/`.tab-section-title`/`.btn`/`.btn-secondary`/`.btn-sm` all already exist in `patient-detail.component.css` (used identically by the "treatments"/"plans" tab headers).

- [ ] **Step 3: Verify manually in the browser (real, observed session)**

Using the Puppeteer pattern from Global Constraints:
1. Open a patient's detail page, click the "Historia Médica" tab. Confirm the new header with "Historia Médica" title and "🖨️ Imprimir" button renders above the antecedentes summary, and the existing "Notas médicas generales" section below is unchanged.
2. Click "🖨️ Imprimir" (or inspect its bound handler/construct the URL) and confirm it opens `/patients/<id>/historia/imprimir` in a new tab, and that tab renders the full document built in Task 6 (not a 404/blank page) — this is the end-to-end confirmation that Tasks 1-7 connect correctly.
3. TypeScript compile check: `docker compose exec frontend ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json` → no errors.
4. `git status --short` shows only the intended diff across all 7 tasks (no stray Puppeteer scripts/screenshots left in the working tree).

- [ ] **Step 4: Commit**

Ask the user before running this.

```bash
git add frontend/src/app/features/patients/patient-detail.component.ts frontend/src/app/features/patients/patient-detail.component.html
git commit -m "feat(frontend): add print button to patient's Historia Médica tab"
```
