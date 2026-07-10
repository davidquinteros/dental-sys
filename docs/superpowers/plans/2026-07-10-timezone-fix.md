# Fix de zona horaria — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Corregir dos bugs sistémicos de zona horaria — instantes UTC mostrados +4h/día equivocado (Bug 1) y fechas-solas mostradas un día antes (Bug 2) — serializando instantes con `Z` en el backend y centralizando el formateo de fechas en el frontend.

**Architecture:** Clasificación por semántica (ver spec). Backend agrega `Z` solo a instantes. Frontend (ambas apps) usa un `date.util.ts` con `formatDate`/`formatDateLong`/`formatDateTime`/`formatTime` (vía `new Date`, correctos con `Z`) y `formatDateOnly` (parseo de `YYYY-MM-DD` sin corrimiento) para campos `db.Date`.

**Tech Stack:** Flask + SQLAlchemy (backend), Angular 18 standalone (frontend/, admin-frontend/), PostgreSQL.

**Spec:** `docs/superpowers/specs/2026-07-10-timezone-fix-design.md`

## Global Constraints

- Commits: **el usuario autorizó comitear en esta sesión** ("anda comiteando los cambios que vayas haciendo"). Comitear por tarea; **no** `push` salvo pedido explícito. Rama `develop`.
- No hay suite de tests. Verificación real: backend por `flask shell`/curl; UI por Puppeteer en el contenedor (chromium + puppeteer-core ya instalados; flag `--host-resolver-rules=MAP localhost:5000 backend:5000`; token en `localStorage['dental_access_token']`). Nada de "verificado por code review".
- Gunicorn sin `--reload`: tras editar `.py`, `docker compose restart backend`.
- **NO tocar**: `Appointment.scheduled_at`, `Clinic.plan_started_at`/`plan_expires_at`, ni la serialización de columnas `db.Date` en el backend. Ver spec para el porqué.
- Strings en español. Credenciales de verificación: clínica `admin@testing.local / Nuo67q7iXfT#` (clinic_id=2), platform `platform-verify@testing.local / Plat67q7iXfT#`.

---

### Task 1: Backend — helper `iso_utc()` y aplicarlo a los campos instante

**Files:**
- Create: `backend/app/utils/serialization.py`
- Modify: `backend/app/models/appointment.py`, `treatment.py`, `treatment_image.py`, `patient.py`, `user.py`, `billing.py`, `clinic.py`, `subscription.py`

**Interfaces:**
- Produces: `iso_utc(dt) -> str | None` — ISO-8601 con sufijo `Z` para datetimes naive-UTC.

- [ ] **Step 1: Crear el helper**

`backend/app/utils/serialization.py`:
```python
def iso_utc(dt):
    """Serializa un datetime naive-UTC como ISO-8601 con sufijo 'Z',
    para que `new Date()` en el frontend lo interprete como UTC (no local).
    Devuelve None si dt es None."""
    return dt.isoformat() + "Z" if dt else None
```

- [ ] **Step 2: Reemplazar en los `to_dict()` — SOLO estos campos instante**

En cada modelo, importar `from app.utils.serialization import iso_utc` y reemplazar
`self.<campo>.isoformat() if self.<campo> else None` → `iso_utc(self.<campo>)` para:

| Archivo | Campos instante |
|---|---|
| `appointment.py` | `created_at`, `completed_at` |
| `treatment.py` | `performed_at`, `created_at` (Treatment); `created_at` (TreatmentPlan) |
| `treatment_image.py` | `created_at` |
| `patient.py` | `created_at` |
| `user.py` | `created_at` |
| `billing.py` | `Invoice.created_at`; `Payment.payment_date`; `PaymentPlanInstallment.payment_date`; `PaymentPlan.created_at` |
| `clinic.py` | `created_at`, `trial_ends_at`, `next_payment_due_at`, `suspended_at` |
| `subscription.py` | `SubscriptionTier.created_at`; `SubscriptionPayment.created_at` |

**NO cambiar** (dejar `.isoformat()`): `Appointment.scheduled_at`; `Clinic.plan_started_at`/`plan_expires_at`; todos los `db.Date` (`Patient.date_of_birth`, `Invoice.due_date`, `PaymentPlan.start_date`, `TreatmentPlan.start_date`/`estimated_end_date`/`actual_end_date`, `SubscriptionPayment.payment_date`/`period_start`/`period_end`).

- [ ] **Step 3: Restart y verificar por flask shell**

```bash
docker compose restart backend
```
Luego, comprobar que un instante termina en `Z` y una fecha-sola / scheduled_at / plan_* NO:
```bash
docker compose exec backend flask shell -c "
from app.models.treatment import Treatment
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.clinic import Clinic
t=Treatment.query.get(23); print('performed_at', t.to_dict()['performed_at'])   # -> ...Z
p=Patient.query.filter(Patient.date_of_birth.isnot(None)).first()
print('date_of_birth', p.to_dict()['date_of_birth'] if p else 'n/a')            # -> YYYY-MM-DD (sin Z)
a=Appointment.query.first(); print('scheduled_at', a.to_dict()['scheduled_at'] if a else 'n/a')  # -> sin Z
c=Clinic.query.get(2); d=c.to_dict(); print('created_at', d['created_at'], '| plan_expires_at', d['plan_expires_at'])  # created_at con Z, plan_expires_at sin Z
"
```
Expected: `performed_at` y `created_at` terminan en `Z`; `date_of_birth`, `scheduled_at`, `plan_expires_at` **no**.

- [ ] **Step 4: Commit**
```bash
git add backend/app/utils/serialization.py backend/app/models/
git commit -m "fix(backend): serialize UTC instant timestamps with Z suffix so clients localize correctly

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: frontend/ — `date.util.ts` y reemplazo de formateadores duplicados

**Files:**
- Create: `frontend/src/app/core/util/date.util.ts`
- Modify (borrar el formateador local y usar imports): `appointments-list.component.ts`, `treatment-detail.component.ts`, `dashboard.component.ts`, `billing.component.ts`, `invoice-detail.component.ts`, `payment-plan-detail.component.ts`, `patient-detail.component.ts`, `patients-list.component.ts`, `treatment-plan-detail.component.ts`, `treatment-receta.component.ts`, `treatments.component.ts`

**Interfaces:**
- Consumes: instantes con `Z` (Task 1).
- Produces: `formatDate`, `formatDateLong`, `formatDateTime`, `formatTime`, `formatDateOnly` (todas `(iso: string | null | undefined) => string`).

- [ ] **Step 1: Crear el módulo**

`frontend/src/app/core/util/date.util.ts`:
```typescript
const LOCALE = 'es-BO';

/** Instantes (con 'Z') y scheduled_at: día (mes corto). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' });
}

/** Instantes y scheduled_at: día (mes largo). */
export function formatDateLong(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(LOCALE, { day: '2-digit', month: 'long', year: 'numeric' });
}

/** Instantes y scheduled_at: día + hora. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
}

/** Instantes y scheduled_at: solo hora. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false });
}

/** Campos db.Date ('YYYY-MM-DD'): formatea SIN corrimiento de zona (mes corto). */
export function formatDateOnly(iso: string | null | undefined): string {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' });
}
```

- [ ] **Step 2: Reemplazar los formateadores locales por imports, con este mapeo exacto**

En cada componente: borrar su(s) método(s) `formatDate`/`formatDateTime`/`formatTime` local(es) y agregar `import { ... } from '../../core/util/date.util';` (ajustar profundidad de ruta según el archivo). Usar la función correcta según el campo:

| Componente (.ts / .html) | Call-site (campo) | Función a usar |
|---|---|---|
| `appointments-list` | `scheduled_at` (date), `scheduled_at` (time) | `formatDate`, `formatTime` |
| `treatment-detail` | `performed_at` (l.16 datetime) / (l.116 date, mes largo) | `formatDateTime`, `formatDateLong` |
| `dashboard` | `scheduled_at` (time, y day/month parts) | `formatTime` (mantener helpers de day/month sobre `scheduled_at` con `new Date`) |
| `billing.component` | `inv.created_at` | `formatDate` |
| `invoice-detail` | `invoice.created_at` | `formatDate` |
| `invoice-detail` | `invoice.due_date` (**db.Date**) | `formatDateOnly` |
| `patient-detail` | `a.scheduled_at` (datetime), `t.performed_at`/`s.performed_at` (date) | `formatDateTime`, `formatDate` |
| `patient-detail` | `date_of_birth` (**db.Date**), `plan.start_date`/`estimated_end_date` (**db.Date**) | `formatDateOnly` |
| `patients-list` | `patient.created_at` | `formatDate` |
| `treatment-plan-detail` | `session.performed_at` | `formatDate` |
| `treatment-plan-detail` | `plan.start_date`/`estimated_end_date` (**db.Date**) | `formatDateOnly` |
| `payment-plan-detail` | `plan.created_at`, `item.payment_date` (instante) | `formatDate` |
| `payment-plan-detail` | `plan.start_date` (**db.Date**) | `formatDateOnly` |
| `treatment-receta` | `performed_at` (mes largo) | `formatDateLong` |
| `treatments` | `t.performed_at` | `formatDate` |
| `treatments` | `plan.start_date` (**db.Date**) | `formatDateOnly` |

Regla para cualquier call-site no listado: si el campo es `db.Date` (`date_of_birth`, `due_date`, `start_date`, `estimated_end_date`, `actual_end_date`, `period_start`, `period_end`, o `SubscriptionPayment.payment_date`) → `formatDateOnly`; si no → `formatDate`/`formatDateTime`/`formatTime`. Donde un `.html` invoque una función que el `.ts` ya no define (p.ej. `formatDateOnly`), agregar el import correspondiente para que el template resuelva (los componentes standalone exponen las funciones importadas si se las asigna como propiedad, o se envuelve en un método — mantener el patrón existente del componente: si hoy el template llama `formatDate(x)`, el componente debe seguir teniendo un miembro con ese nombre; la forma más simple es re-exportar: `formatDate = formatDate;` NO válido por shadowing — en su lugar declarar métodos delgados `formatDate = (iso) => fmtDate(iso)` importando con alias, o importar y asignar `protected readonly formatDateOnly = formatDateOnly;`).

> Nota de implementación Angular: como los templates llaman a los formateadores como miembros del componente, importar las funciones con alias y exponerlas como propiedades del componente, p.ej.:
> ```typescript
> import { formatDate as fmtDate, formatDateOnly as fmtDateOnly, formatDateTime as fmtDateTime, formatTime as fmtTime, formatDateLong as fmtDateLong } from '../../core/util/date.util';
> // dentro de la clase:
> protected readonly formatDate = fmtDate;
> protected readonly formatDateOnly = fmtDateOnly;
> protected readonly formatDateTime = fmtDateTime;
> protected readonly formatTime = fmtTime;
> protected readonly formatDateLong = fmtDateLong;
> ```
> y en el `.html` cambiar el nombre de la función solo donde la tabla indica `formatDateOnly`/`formatDateLong`.

- [ ] **Step 3: Verificar recompilación**
```bash
docker compose logs --tail 40 frontend
```
Esperar rebuild limpio, sin errores TS/template.

- [ ] **Step 4: Verificación en navegador (Puppeteer)**

Script en `/tmp` del contenedor `frontend` (patrón ya usado): login como `admin@testing.local`, y comprobar:
1. `/treatments/23/receta` → "Fecha" muestra el día local correcto de `performed_at` (con `Z`, `new Date` lo localiza; si `performed_at` cae 00:00–04:00 UTC, debe verse el día anterior local, no el UTC).
2. patient-detail de un paciente con `date_of_birth` conocido → la fecha de nacimiento coincide exacta (no un día antes).
3. `/appointments` y calendario → hora de la cita **igual** a la agendada (regresión: sin corrimiento).
Registrar screenshots como evidencia.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/app/core/util/date.util.ts frontend/src/app/features/
git commit -m "fix(frontend): centralize date formatting; render UTC instants and date-only fields in correct local day

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: admin-frontend/ — `date.util.ts` y reemplazo de formateadores

**Files:**
- Create: `admin-frontend/src/app/core/util/date.util.ts` (copia del módulo de Task 2)
- Modify: `admin-frontend/src/app/features/dashboard/dashboard.component.ts`, `clinics/clinic-detail.component.ts`, `clinics/clinics-list.component.ts`

**Interfaces:**
- Consumes: instantes con `Z` (Task 1).

- [ ] **Step 1: Crear el módulo**

Copiar el mismo `date.util.ts` de Task 2 en `admin-frontend/src/app/core/util/date.util.ts` (contenido idéntico).

- [ ] **Step 2: Reemplazar formateadores con este mapeo**

| Componente | Call-site (campo) | Función |
|---|---|---|
| `dashboard` | `c.next_payment_due_at` (instante) | `formatDate` |
| `clinics-list` | `c.next_payment_due_at` (instante), `c.plan_expires_at` (medianoche naive) | `formatDate` |
| `clinic-detail` | `clinic.created_at` (instante), `plan_started_at`/`plan_expires_at` (medianoche naive) | `formatDate` |
| `clinic-detail` | `p.payment_date`, `p.period_start`, `p.period_end` (**db.Date**) | `formatDateOnly` |

`plan_started_at`/`plan_expires_at` siguen usando `formatDate` (`new Date` sobre medianoche naive = día correcto). `daysRemaining()` y `toDateInput()` **no cambian**. Exponer las funciones importadas como miembros del componente igual que en Task 2 (alias + `protected readonly`).

- [ ] **Step 3: Verificar recompilación**
```bash
docker compose logs --tail 40 admin-frontend
```
Rebuild limpio.

- [ ] **Step 4: Verificación en navegador (Puppeteer, :4300)**

Login como `platform-verify@testing.local`, abrir clinic-detail de la clínica 2: verificar que `payment_date`/`period_start`/`period_end` de los pagos de suscripción muestran el día exacto (no un día antes) y que `Fecha de registro`/fechas de plan se ven correctas. Screenshot.

- [ ] **Step 5: Commit**
```bash
git add admin-frontend/src/app/core/util/date.util.ts admin-frontend/src/app/features/
git commit -m "fix(admin-frontend): centralize date formatting; correct local day for instants and date-only fields

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review (cobertura del spec)
- Bug 1 (instantes +4h/día) → Task 1 (Z) + Task 2/3 (`new Date` ya correcto). ✅
- Bug 2 (fechas-solas un día antes) → Task 2/3 (`formatDateOnly` en call-sites `db.Date`). ✅
- Centralización de formateadores → Task 2/3 (`date.util.ts`). ✅
- No tocar scheduled_at / plan_* / serialización db.Date → constraints + tablas de mapeo. ✅
- Verificación real (recetario, fecha nacimiento, regresión de citas) → Task 2 Step 4. ✅

## Notas de despliegue
Sin migración de DB (solo cambia serialización/formateo). Al desplegar a testing/prod, basta con el deploy de código habitual.
