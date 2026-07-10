# Mejoras al recetario — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mejorar el recetario estructurado — duración seleccionable + indicaciones por medicamento en el formulario, email de contacto de la clínica, y rediseño de la vista imprimible (dos logos, info centrada, medicamentos numerados).

**Architecture:** Cambio full-stack sobre la feature FCLI-11 existente. `medications` es JSON libre (la clave `indications` no requiere migración). Se agrega una columna `Clinic.email` (única migración de esquema). El logo My Dental Sys es un asset estático provisto por el usuario.

**Tech Stack:** Flask + SQLAlchemy + Alembic (backend), Angular 18 standalone + signals (frontend y admin-frontend), PostgreSQL (Supabase testing, compartida en local).

## Global Constraints

- **Nunca `git commit`/`git push` automático.** Cada "Checkpoint de commit" es un punto donde el implementador PARA y el usuario comitea manualmente. El implementador jamás corre `git commit`/`git add`/`git push`.
- **No hay suite de tests automatizada** (ni pytest ni specs de karma). La verificación es real: `curl`/Swagger para backend, y navegador (Puppeteer dentro del contenedor `frontend`/`admin-frontend`, patrón de CLAUDE.md) para UI. Nada de "verificado por code review".
- **Gunicorn sin `--reload`:** todo cambio `.py` requiere `docker compose restart backend` para surtir efecto.
- **Migraciones:** correr con el rol de migraciones — `DATABASE_URL="$MIGRATIONS_DATABASE_URL" flask db upgrade`. La DB local ES la de testing (destructivo real, pero agregar columna nullable es seguro). Render no migra solo: el `flask db upgrade` en testing/prod es manual al desplegar.
- **Idioma:** todas las strings de UI y mensajes en español.
- **Head de Alembic actual:** `b7e4f91a2c3d`. La nueva migración encadena ahí.

---

### Task 1: Backend — columna `Clinic.email` + migración + exposición en API

**Files:**
- Modify: `backend/app/models/clinic.py` (columna + `to_dict`)
- Create: `backend/migrations/versions/c8f5a2e91b4d_add_clinic_email.py`
- Modify: `backend/app/routes/clinic.py` (`clinic_info` respuesta)
- Modify: `backend/app/routes/platform_admin.py` (`update_clinic` acepta email)

**Interfaces:**
- Produces: `GET /api/clinic/info` devuelve `email`; `PUT /api/platform/clinics/<id>` acepta `email`; `Clinic.to_dict()` incluye `"email"`.

- [ ] **Step 1: Agregar la columna al modelo**

En `backend/app/models/clinic.py`, junto a `logo_url` (línea ~19):

```python
    logo_url = db.Column(db.String(500), nullable=True)
    email = db.Column(db.String(255), nullable=True)  # Email de contacto (encabezado del recetario)
```

En `to_dict()`, junto a `"logo_url": self.logo_url,` (línea ~75):

```python
            "logo_url": self.logo_url,
            "email": self.email,
```

- [ ] **Step 2: Crear la migración a mano**

Crear `backend/migrations/versions/c8f5a2e91b4d_add_clinic_email.py`:

```python
"""add email column to clinics

Revision ID: c8f5a2e91b4d
Revises: b7e4f91a2c3d
Create Date: 2026-07-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8f5a2e91b4d'
down_revision = 'b7e4f91a2c3d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.drop_column('email')
```

- [ ] **Step 3: Aplicar la migración (rol de migraciones)**

Run:
```bash
docker compose exec backend sh -c 'DATABASE_URL="$MIGRATIONS_DATABASE_URL" flask db upgrade'
```
Expected: `Running upgrade b7e4f91a2c3d -> c8f5a2e91b4d, add email column to clinics`

- [ ] **Step 4: Exponer email en `clinic_info`**

En `backend/app/routes/clinic.py`, en el dict de respuesta de `clinic_info()` (junto a `"logo_url": clinic.logo_url,`):

```python
        "logo_url": clinic.logo_url,
        "email": clinic.email,
```
Agregar `email:` a la sección `properties` del docstring Swagger de ese endpoint (junto a `logo_url:` / `phone:`), con `type: string`.

- [ ] **Step 5: Aceptar email en `update_clinic`**

En `backend/app/routes/platform_admin.py`, en `update_clinic()`, junto al bloque de `phone` (línea ~348):

```python
    if "phone" in data:
        clinic.phone = data["phone"]
    if "email" in data:
        clinic.email = data["email"]
```
Agregar `email:` (type: string) al docstring Swagger del request body de ese endpoint.

- [ ] **Step 6: Reiniciar backend y verificar por API**

Run:
```bash
docker compose restart backend
# login como platform admin -> token; luego:
curl -s -X PUT http://localhost:5000/api/platform/clinics/1 \
  -H "Authorization: Bearer <PLATFORM_TOKEN>" -H "Content-Type: application/json" \
  -d '{"email":"contacto@clinica.test"}' | grep email
# login como staff de la clínica 1 -> token; luego:
curl -s http://localhost:5000/api/clinic/info -H "Authorization: Bearer <STAFF_TOKEN>" | grep email
```
Expected: el PUT devuelve `"email":"contacto@clinica.test"` en el `clinic`; el GET `/clinic/info` devuelve el mismo email.

- [ ] **Step 7: Checkpoint de commit (el usuario comitea)**

Archivos: `backend/app/models/clinic.py`, `backend/migrations/versions/c8f5a2e91b4d_add_clinic_email.py`, `backend/app/routes/clinic.py`, `backend/app/routes/platform_admin.py`. Mensaje sugerido: `feat(backend): add editable clinic email exposed on clinic-info and platform update`. PARAR — no comitear automáticamente.

---

### Task 2: admin-frontend — editar el email de la clínica

**Files:**
- Modify: `admin-frontend/src/app/core/models/index.ts` (`Clinic.email`)
- Modify: `admin-frontend/src/app/features/clinics/clinic-detail.component.ts` (`editForm`)
- Modify: `admin-frontend/src/app/features/clinics/clinic-detail.component.html` (campo email)

**Interfaces:**
- Consumes: `PUT /api/platform/clinics/<id>` con `email` (Task 1).

- [ ] **Step 1: Agregar `email` al modelo `Clinic`**

En `admin-frontend/src/app/core/models/index.ts`, en la interfaz `Clinic`, junto a los campos de contacto:

```typescript
  email?: string | null;
```

- [ ] **Step 2: Agregar `email` a `editForm` y poblarlo**

En `clinic-detail.component.ts`, en la definición de `editForm` (línea ~27):

```typescript
    address: '', phone: '', email: '',
```
Y en el bloque que puebla `editForm` desde `d.clinic` (línea ~71):

```typescript
          address: d.clinic.address || '',
          phone: d.clinic.phone || '',
          email: d.clinic.email || '',
```
(El payload del PUT ya hace `...this.editForm`, así que `email` viaja sin cambios extra.)

- [ ] **Step 3: Agregar el campo email al HTML (Ver y Editar)**

En `clinic-detail.component.html`, replicar exactamente el patrón del campo `phone` (label + input en modo Editar, texto en modo Ver) para `email`, usando `[(ngModel)]="editForm.email"`, `type="email"`, placeholder `Ej: contacto@clinica.com`, y en modo Ver mostrando `clinic.email` con un fallback (p.ej. `—`) cuando esté vacío. Colocarlo inmediatamente después del campo de teléfono.

- [ ] **Step 4: Verificar en el navegador (admin-frontend :4300)**

Levantar admin-frontend, iniciar sesión como platform admin, abrir clinic-detail de la clínica 1:
1. Modo Ver muestra el email guardado en Task 1 (`contacto@clinica.test`).
2. "Editar" → cambiar el email → Guardar → recargar la página → el nuevo valor persiste.

Verificación con Puppeteer (o navegador host si está disponible). Registrar evidencia (screenshot / valor leído del DOM), no "code review".

- [ ] **Step 5: Checkpoint de commit (el usuario comitea)**

Archivos: los tres de admin-frontend de esta tarea. Mensaje sugerido: `feat(admin-frontend): edit clinic contact email in clinic-detail`. PARAR.

---

### Task 3: frontend — duración seleccionable + indicaciones por medicamento (formulario)

**Files:**
- Modify: `frontend/src/app/core/models/index.ts` (`Medication.indications`)
- Modify: `frontend/src/app/features/treatments/treatment-form.component.ts`
- Modify: `frontend/src/app/features/treatments/treatment-form.component.html`

**Interfaces:**
- Produces: cada medicamento guardado puede incluir `indications?: string`; `duration` se guarda como una de las etiquetas del dropdown o el texto libre de "Otro".

- [ ] **Step 1: Agregar `indications` al modelo `Medication`**

En `frontend/src/app/core/models/index.ts`, en la interfaz `Medication` (junto a `duration?`):

```typescript
  duration?: string;
  indications?: string;
```

- [ ] **Step 2: Agregar la lista de duraciones y ampliar el FormGroup**

En `treatment-form.component.ts`, junto a `medicationForms` (línea ~28):

```typescript
  readonly durationOptions = [
    '1 día', '2 días', '3 días', '4 días', '5 días', '6 días', '7 días', 'Otro',
  ];
```

Reemplazar `newMedicationGroup()` (líneas ~72–84) por:

```typescript
  private newMedicationGroup(med?: Medication): FormGroup {
    const presetForms = this.medicationForms.slice(0, -1);
    const isOtherForm = !!med?.form && !presetForms.includes(med.form);
    const presetDurations = this.durationOptions.slice(0, -1);
    const isOtherDuration = !!med?.duration && !presetDurations.includes(med.duration);
    return this.fb.group({
      name: [med?.name ?? '', Validators.required],
      concentration: [med?.concentration ?? ''],
      form: [isOtherForm ? 'Otro' : (med?.form ?? '')],
      form_custom: [isOtherForm ? med!.form : ''],
      quantity: [med?.quantity ?? ''],
      dosage: [med?.dosage ?? '', Validators.required],
      duration: [isOtherDuration ? 'Otro' : (med?.duration ?? '')],
      duration_custom: [isOtherDuration ? med!.duration : ''],
      indications: [med?.indications ?? ''],
    });
  }
```

- [ ] **Step 3: Mapear los nuevos campos al guardar**

En `treatment-form.component.ts`, en el `.map` de `medications` (líneas ~240–250), reemplazar el `return` por:

```typescript
      return {
        name: g.name,
        concentration: g.concentration || null,
        form: g.form === 'Otro' ? (g.form_custom || null) : (g.form || null),
        quantity: g.quantity || null,
        dosage: g.dosage,
        duration: g.duration === 'Otro' ? (g.duration_custom || null) : (g.duration || null),
        indications: g.indications || null,
      };
```

- [ ] **Step 4: Cambiar el input de duración por un select + custom, y agregar indicaciones**

En `treatment-form.component.html`, reemplazar el `form-group` de duración (líneas ~236–239) por:

```html
                <div class="form-group">
                  <label>Duración</label>
                  <select formControlName="duration">
                    <option value="">Seleccionar...</option>
                    @for (d of durationOptions; track d) {
                      <option [value]="d">{{ d }}</option>
                    }
                  </select>
                </div>
```

Inmediatamente después del `</div>` que cierra ese `form-row-3` (línea ~240), agregar el custom de duración y el campo de indicaciones:

```html
              @if (med.get('duration')?.value === 'Otro') {
                <div class="form-group">
                  <label>Especifique la duración</label>
                  <input formControlName="duration_custom" type="text" placeholder="Ej: 10 días"/>
                </div>
              }
              <div class="form-group">
                <label>Indicaciones</label>
                <input formControlName="indications" type="text" placeholder="Ej: Tomar con alimentos"/>
              </div>
```

- [ ] **Step 5: Verificar en el navegador (frontend :4200)**

Con Puppeteer (patrón CLAUDE.md, `--host-resolver-rules=MAP localhost:5000 backend:5000`):
1. Crear/editar una atención con receta: la duración se elige del dropdown; seleccionar "Otro" muestra el input de texto; escribir indicaciones.
2. Guardar → reabrir en modo edición → la duración vuelve seleccionada (o "Otro" + custom si fue libre) y las indicaciones reaparecen.
3. Editar una atención vieja con duración libre (p.ej. "5 dias") → debe caer en "Otro" con el texto en el custom (detección `isOtherDuration`).

Registrar evidencia real (screenshot / lectura del componente vía `window.ng.getComponent`).

- [ ] **Step 6: Checkpoint de commit (el usuario comitea)**

Archivos: `frontend/src/app/core/models/index.ts`, `treatment-form.component.ts`, `treatment-form.component.html`. Mensaje sugerido: `feat(frontend): selectable medication duration and per-medication indications`. PARAR.

---

### Task 4: frontend — rediseño del recetario imprimible

**Files:**
- Modify: `frontend/src/app/core/models/index.ts` (`ClinicInfo.email`)
- Modify: `frontend/src/app/features/treatments/treatment-receta.component.html`
- Modify: `frontend/src/app/features/treatments/treatment-receta.component.css`
- Create: `frontend/src/assets/mydentalsys-logo.svg` (placeholder hasta recibir el archivo del usuario)

**Interfaces:**
- Consumes: `ClinicInfo.email` (Task 1 backend), `Medication.indications` (Task 3).

- [ ] **Step 1: Agregar `email` a `ClinicInfo`**

En `frontend/src/app/core/models/index.ts`, en la interfaz `ClinicInfo` (junto a `logo_url?`):

```typescript
  logo_url?: string;
  email?: string;
```

- [ ] **Step 2: Colocar el asset del logo My Dental Sys**

Crear `frontend/src/assets/` si no existe. Colocar `mydentalsys-logo.svg` provisto por el usuario. Si aún no llegó, crear un placeholder SVG con wordmark "My Dental Sys" para no romper el build; se reemplaza al recibir el archivo definitivo (mismo nombre de archivo → sin más cambios de código). Confirmar que `angular.json` incluye `src/assets` en `assets` (por defecto lo hace en proyectos Angular; verificar).

- [ ] **Step 3: Rediseñar la cabecera y los medicamentos en el HTML**

En `treatment-receta.component.html`, reemplazar el `<header>` (líneas ~7–16) por una cabecera de tres zonas:

```html
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

Reemplazar el `@for` de medicamentos (líneas ~31–38) por la versión numerada + indicaciones:

```html
      @for (med of treatment()!.medications; track $index; let i = $index) {
        <div class="medication-item">
          <p class="med-name">{{ i + 1 }}. {{ med.name }}{{ med.concentration ? ' — ' + med.concentration : '' }}</p>
          <p class="med-detail">
            {{ med.form || '—' }} · Cantidad: {{ med.quantity || '—' }} · Dosis: {{ med.dosage }}{{ med.duration ? ' · Duración: ' + med.duration : '' }}
          </p>
          @if (med.indications) {
            <p class="med-indications"><em>Indicaciones: {{ med.indications }}</em></p>
          }
        </div>
      }
```

- [ ] **Step 4: Estilos de la nueva cabecera y de indicaciones**

En `treatment-receta.component.css`:
- `.receta-header`: `display: flex; align-items: center; justify-content: space-between; gap: 1rem;` (mantener la línea inferior/borde existente).
- `.header-side`: ancho fijo/mín. para ambos lados (p.ej. `flex: 0 0 90px`) para que el bloque central quede realmente centrado; `.header-right` alinea su contenido a la derecha.
- `.clinic-info`: `flex: 1; text-align: center;`.
- `.clinic-logo` y `.system-logo`: `max-height: 64px; max-width: 100%; object-fit: contain;`.
- `.med-indications`: color gris (p.ej. `#666`), tamaño levemente menor, margen superior mínimo.
- Verificar que en `@media print` los logos y el layout centrado se conserven.

- [ ] **Step 5: Verificar en el navegador (frontend :4200)**

Con Puppeteer:
1. Abrir el recetario de una atención con varios medicamentos (incluyendo uno con indicaciones y una duración "Otro").
2. Confirmar: logo clínica a la izquierda, logo My Dental Sys a la derecha, bloque central (nombre/dirección/teléfono/email) centrado; medicamentos "1.", "2."…; línea "Indicaciones: …" bajo el que corresponde.
3. Emular impresión (`page.emulateMediaType('print')` o screenshot) y confirmar que el layout se mantiene.

Screenshot como evidencia.

- [ ] **Step 6: Checkpoint de commit (el usuario comitea)**

Archivos: `frontend/src/app/core/models/index.ts`, `treatment-receta.component.html`, `treatment-receta.component.css`, `frontend/src/assets/mydentalsys-logo.svg`. Mensaje sugerido: `feat(frontend): redesign printable recetario header and medication list`. PARAR.

---

## Self-review (cobertura del spec)

- Clinic.email editable desde admin-frontend + migración + API → Task 1 + Task 2. ✅
- `medications` gana `indications` sin migración → Task 3 (modelo/form) + Task 4 (impresión). ✅
- Duración select 1–7 + "Otro" con detección de valores libres previos → Task 3. ✅
- Cabecera: logo clínica izq., My Dental Sys der., info centrada + email → Task 4. ✅
- Medicamentos numerados + indicaciones con etiqueta → Task 4. ✅
- Compatibilidad hacia atrás (sin indications / email / duraciones libres) → cubierta por los `@if` y la detección `isOtherDuration`. ✅

## Notas de despliegue (Entrega 1)

Al mergear a `testing`/`main`, correr manualmente el `flask db upgrade` (con el rol de migraciones) contra cada Supabase antes/junto con el deploy del código, y subir el asset definitivo del logo My Dental Sys.
