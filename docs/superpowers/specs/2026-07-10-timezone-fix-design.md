# Fix de zona horaria — Diseño

**Fecha:** 2026-07-10
**Rama:** `develop`
**Alcance:** Bug 1 (instantes UTC mostrados +4h / día equivocado) + Bug 2 (fechas-solas mostradas un día antes). El ajuste menor de `plan_expires_at` (vencimiento a medianoche UTC vs local) queda **fuera** de esta entrega.

## Contexto y causa raíz

El backend serializa datetimes *naive* con `.isoformat()` (sin offset ni `Z`). El frontend usa `new Date(iso)` en todos lados. JavaScript parsea:
- datetime **sin** offset → como hora **local**
- fecha-sola `YYYY-MM-DD` → como **UTC** medianoche

Verificado con Node bajo `TZ=America/La_Paz` (UTC-4):

| String backend | `new Date().toLocaleDateString('es-BO')` | Correcto |
|---|---|---|
| `2026-07-10T02:13:52` (instante UTC) | `10/7/2026` | ❌ (debería 9/7) |
| `2026-07-10T02:13:52Z` | `9/7/2026` | ✅ objetivo |
| `2026-07-15T14:30:00` (scheduled_at local) | `15/7/2026` | ✅ ya correcto |
| `1990-05-15` (fecha-sola) | `14/5/1990` | ❌ un día antes |

## Principio del fix: clasificar por semántica

Cada campo fecha/hora cae en una de cuatro clases. El fix trata cada clase distinto:

1. **Instante** (un momento preciso, `db.DateTime` con default `utcnow`): el valor real es UTC. **Backend** lo serializa con `Z`. **Frontend** lo muestra con `new Date()` (ya correcto tras el `Z`).
2. **Fecha calendario** (`db.Date`, un día sin hora): **Backend** sigue serializando `YYYY-MM-DD` (sin cambio). **Frontend** lo formatea **sin** `new Date()` (parseo de las partes), para evitar el corrimiento.
3. **Fecha-a-medianoche naive** (`db.DateTime` seteado desde un date-picker a medianoche: `plan_started_at`, `plan_expires_at`): **hoy se muestra correcto** (`new Date` lo parsea como medianoche local = mismo día). **No se toca.**
4. **Hora local de pared** (`scheduled_at`): naive-local, consistente extremo a extremo. **No se toca.** `clinic_time.py` (`local_now`/`local_today`) ya mantiene correctas las comparaciones del backend.

## Clasificación de todos los campos (inventario de `to_dict()`)

**Instantes → agregar `Z` en backend:**
- `Appointment`: `created_at`, `completed_at`
- `Treatment`: `performed_at`, `created_at`
- `TreatmentPlan`: `created_at`
- `TreatmentImage`: `created_at`
- `Patient`: `created_at`
- `User`: `created_at`
- `Invoice`: `created_at`
- `Payment`: `payment_date` (db.DateTime), y `created_at` si aparece en su `to_dict`
- `PaymentPlanInstallment`: `payment_date` (db.DateTime)
- `PaymentPlan`: `created_at`
- `Clinic`: `created_at`, `trial_ends_at`, `next_payment_due_at`, `suspended_at`
- `SubscriptionTier`: `created_at`
- `SubscriptionPayment`: `created_at`

**Fechas calendario (`db.Date`) → sin cambio en backend; formatear sin corrimiento en frontend:**
- `Patient`: `date_of_birth`
- `Invoice`: `due_date`
- `PaymentPlan`: `start_date`
- `TreatmentPlan`: `start_date`, `estimated_end_date`, `actual_end_date`
- `SubscriptionPayment`: `payment_date`, `period_start`, `period_end`

**Sin tocar:** `Appointment.scheduled_at` (local wall-clock), `Clinic.plan_started_at` / `plan_expires_at` (medianoche naive, ya correctos).

> El plan de implementación hará el mapeo exhaustivo call-site por call-site en el frontend; esta tabla es la fuente de verdad de la clasificación.

## Cambios por capa

### Backend
Nuevo helper `backend/app/utils/serialization.py`:
```python
def iso_utc(dt):
    """ISO-8601 de un datetime naive-UTC con sufijo 'Z' (para que JS lo parse como UTC)."""
    return dt.isoformat() + "Z" if dt else None
```
Reemplazar en los `to_dict()` de los modelos, **solo para los campos de la lista "Instantes"**:
`self.<campo>.isoformat() if self.<campo> else None` → `iso_utc(self.<campo>)`.
Los `db.Date` y `scheduled_at`/`plan_*` quedan con `.isoformat()` como están.

### Frontend (`frontend/` y `admin-frontend/` — cada app su copia)
Nuevo módulo `core/util/date.util.ts` con funciones puras exportadas:
```typescript
const LOCALE = 'es-BO';

/** Instantes (con 'Z') y scheduled_at (local): día. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' });
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

/** Campos db.Date ('YYYY-MM-DD'): formatea SIN corrimiento de zona. */
export function formatDateOnly(iso: string | null | undefined): string {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' });
}
```
Notas:
- Las variantes con `month: 'long'` (p.ej. la "Fecha" del recetario, treatment-detail) se cubren con un parámetro de opciones o una función hermana `formatDateLong` — el plan define la firma final para no perder los formatos actuales.
- Cada componente reemplaza su `formatDate`/`formatDateTime`/`formatTime` local por un import del módulo. **Los call-sites de campos `db.Date`** (fecha de nacimiento, `due_date`, `start_date`, `period_*`, `estimated/actual_end_date`, `SubscriptionPayment.payment_date`) usan `formatDateOnly`; el resto usa `formatDate`/`formatDateTime`.
- `substring(0,10)` / `substring(0,16)` para inputs (`patient-form` date_of_birth, `appointment-form` scheduled_at) **no cambian** (operan sobre el string crudo, no muestran; `scheduled_at` y las fechas-solas conservan su formato).

## Qué NO cambia (y por qué)
- `scheduled_at`, calendario y disponibilidad de citas: ya correctos (naive-local + `clinic_time.py`). Tocarlos sería el enfoque C (rechazado por riesgo/migración).
- `plan_started_at`/`plan_expires_at`: medianoche naive, se muestran bien hoy; agregarles `Z` los correría un día.
- Serialización de columnas `db.Date` en backend: ya emiten `YYYY-MM-DD`, correcto; el fix es de display.
- La comparación `access_blocked()` (`plan_expires_at` vs `utcnow`): es el ajuste menor, fuera de alcance.

## Compatibilidad hacia atrás
- Ningún dato almacenado cambia; solo cambia la representación en el borde (serialización con `Z`) y el formateo de display. No hay migración de DB.
- Instantes que hoy se ven +4h pasarán a verse en hora local real (corrección visible, esperada).
- Fechas-solas dejan de correrse un día.

## Verificación (Puppeteer, patrón del proyecto)
1. **Recetario**: una atención con `performed_at` entre 00:00–04:00 UTC muestra el día local correcto (no el siguiente).
2. **Fecha de nacimiento**: un paciente con `date_of_birth` conocido muestra el día exacto (no un día antes) en patient-detail/lista.
3. **Facturación**: `due_date`/`start_date` de un plan muestran el día correcto; `payment_date` (instante) muestra hora local correcta.
4. **Citas (regresión)**: el calendario y la lista siguen mostrando la hora tal cual se agendó (sin corrimiento).
5. **admin-frontend**: fechas de clínica/suscripción muestran el valor correcto.

## Fuera de alcance
- Ajuste de `plan_expires_at` para cortar a medianoche local (menor).
- Normalizar `scheduled_at` a UTC (enfoque C).
