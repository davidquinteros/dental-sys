# Referencia a Plan de Tratamiento en Citas — Design Spec

**Fecha:** 2026-07-06
**Estado:** Aprobado

## Contexto

El backend ya soporta `Appointment.treatment_plan_id` (columna, FK, relación, y se devuelve en `to_dict()`) y `POST /appointments` ya lo acepta, pero **ninguna UI del frontend lo expone hoy**: el formulario de agendar cita no tiene un campo para elegirlo, y ninguna tabla de citas (lista, dashboard, pestañas del paciente) lo muestra. Esta feature completa esa plomería, permitiendo asociar (opcionalmente) una cita a un plan de tratamiento activo del paciente, y mostrar esa referencia en todas las tablas relevantes.

De paso se descubrió que la pestaña "Atenciones" del detalle de paciente tampoco muestra hoy una columna "Plan" pese a que `Treatment.treatment_plan_id` también existe — se agrega ahí también para consistencia.

## Alcance

### 1. Backend

- **`backend/app/models/appointment.py`** — `Appointment.to_dict()` agrega `treatment_plan_name`: el nombre del `TreatmentPlan` asociado (`self.treatment_plan.name` si `treatment_plan_id` está seteado, si no `None`). Sigue el mismo patrón denormalizado que `patient_name`/`doctor_name` en el mismo método.
- **`backend/app/models/treatment.py`** — `Treatment.to_dict()` agrega el mismo campo `treatment_plan_name`, para poder mostrar la columna Plan en la pestaña Atenciones.
- **`backend/app/routes/appointments.py`** — `update_appointment()` (`PUT /appointments/<id>`) agrega `treatment_plan_id` a los campos editables (ya lo es `session_number`). Sin restricción adicional de negocio: se puede asociar/desasociar/cambiar el plan de una cita ya creada en cualquier momento (mientras la cita exista).
- **N+1**: agregar `joinedload(Appointment.treatment_plan)` en `list_appointments`, `get_appointment`, `today_appointments` y el endpoint de calendario; agregar `joinedload(Treatment.treatment_plan)` en el listado de tratamientos. Aplicar también donde `patients/<id>/history` arma `appointments`/`treatments`.
- Sin cambios en `POST /appointments` (ya acepta `treatment_plan_id`/`session_number`).
- Sin cambios en `GET /treatments/plans?patient_id=X&status=active` (ya existe y sirve para poblar el dropdown).

### 2. Formulario "Agendar Cita" (`appointment-form.component.ts` / `.html`)

- Nuevos controles del form, ambos opcionales: `treatment_plan_id` y `session_number` (numérico).
- Al tener un paciente seleccionado (`selectedPatient()` con valor, ya sea por selección manual o `presetPatient`), disparar `treatmentService.getPlans({ patient_id: id, status: 'active' })` y poblar un signal `patientPlans`.
- Nuevo `<select>` "Plan de Tratamiento (opcional)" con opción "Ninguno" (`value=''`) + una opción por cada plan activo del paciente (mostrando `plan.name`).
- Cuando el select tiene un plan elegido (`treatment_plan_id` truthy), mostrar el input numérico "N° de sesión (opcional)"; si se deselecciona el plan, limpiar `session_number` a null.
- Si cambia el paciente seleccionado, resetear `treatment_plan_id`/`session_number` y recargar `patientPlans` para el nuevo paciente (evita arrastrar el plan de un paciente distinto).
- `loadAppointment()` (modo edición): además de los campos actuales, precargar `treatment_plan_id`/`session_number` desde la cita, y disparar la carga de planes del paciente (una vez resuelto `selectedPatient`) para que el `<select>` pueda mostrar la opción ya seleccionada aunque el plan no esté "activo" en este momento (edge case: incluir el plan actual de la cita en la lista aunque su status ya no sea `active`, para no perder la selección existente al editar).
- `onSubmit()`: el payload ya usa `...this.form.value`, así que los nuevos controles viajan automáticamente; no hace falta tocar esa parte. Enviar `null` (no `''`) cuando no hay plan/sesión seleccionados.

### 3. Tablas de citas — columna "Plan"

Se agrega una columna "Plan" en:

- **`appointments-list.component`** (lista standalone `/appointments`).
- **Dashboard** (`dashboard.component.html`): sección "Citas de Hoy" y sección "Próximas Citas".
- **`patient-detail.component.html`**: pestaña "Citas" y pestaña "Atenciones".

**Contenido de la celda:**
- Si hay `treatment_plan_id`: `"{{ treatment_plan_name }} (sesión {{ session_number }})"` — el número de sesión solo se agrega si `session_number` tiene valor; si no, solo el nombre del plan.
- Si no hay `treatment_plan_id`: `—`.
- El nombre del plan (cuando existe) es un link clickeable (ver navegación abajo).

### 4. Navegación al detalle del plan

Reutiliza el modal de detalle de plan que ya existe en `patient-detail.component` (`openPlanDetail(planId)`, ya implementado — carga el plan vía `treatmentService.getPlan()` y abre `showPlanDetailModal`).

- **Dentro de `patient-detail.component`** (pestañas Citas y Atenciones, mismo componente): el link del nombre del plan llama directo a `openPlanDetail(planId)` — sin navegación, abre el modal en el momento.
- **Fuera de `patient-detail`** (lista standalone de citas, dashboard): el link navega con el mismo patrón ya usado en `appointments-list.component.html:163` (`[routerLink]="['/patients', patientId]" [queryParams]="{tab:'appointments'}"`), extendido a `{ tab: 'plans', planId: X }`.
- **`patient-detail.component.ts` `ngOnInit()`**: además de leer `tab` (ya lo hace, línea 74-75), leer `planId` de `queryParamMap`; si está presente, llamar `this.openPlanDetail(+planId)` directamente (no depende de que `plans()` ya esté cargado, porque `openPlanDetail` hace su propio fetch por id).

## Fuera de alcance

- No se agrega un endpoint nuevo (se reutiliza `GET /treatments/plans?patient_id=X&status=active` y `GET /treatments/plans/:id`).
- No se restringe qué estados de cita pueden asociarse a un plan (scheduled/completed/etc. — no aplica ninguna regla nueva).
- No se toca `POST /appointments` (ya soporta los campos).
- No se construye una vista de detalle de plan standalone independiente de `patient-detail` — se acepta la navegación con query params como mecanismo único.

## Testing / verificación

- Sin suite de tests automatizada en este repo (backend ni frontend) — verificar manualmente:
  1. Agendar una cita nueva eligiendo un plan activo + número de sesión → verificar que aparece en la tabla de citas del paciente, en `/appointments`, y en el dashboard (si es hoy/próxima).
  2. Editar una cita existente para asociarle un plan (o cambiarlo) vía `PUT` → confirmar que persiste tras recargar.
  3. Click en el nombre del plan desde `/appointments` y desde el dashboard → confirma que navega a la ficha del paciente, pestaña Planes, y abre el modal del plan correcto.
  4. Click en el nombre del plan desde dentro de patient-detail (pestaña Citas/Atenciones) → confirma que abre el modal sin navegar.
  5. Confirmar que una cita sin plan asociado muestra `—` en todas las tablas.
