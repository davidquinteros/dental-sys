# Recetario Estructurado Imprimible (FCLI-11) — Design Spec

**Fecha:** 2026-07-07
**Estado:** Aprobado
**Jira:** [FCLI-11](https://dentalsys.atlassian.net/browse/FCLI-11) — Recetario estructurado imprimible por atención clínica

## Contexto

Hoy las prescripciones de una atención (`Treatment.prescriptions`) se guardan en un único `textarea` libre y se muestran como párrafo plano en el detalle. Esta feature lo reemplaza por un recetario estructurado: un switch "¿Con receta?" en el formulario de atención, un editor repetible de medicamentos, y una vista imprimible dedicada con los datos de la clínica, el paciente, los medicamentos y la firma del médico.

El diseño UI/UX de la maqueta ya fue aprobado externamente (ticket de Jira) antes de esta sesión; este documento formaliza las decisiones técnicas tomadas durante el brainstorming, incluyendo dos vacíos que el ticket no cubría (ver "Decisiones no cubiertas por el ticket" abajo).

## Alcance

### 1. Modelo de datos (aditivo, no rompe registros legacy)

**`backend/app/models/treatment.py` — `Treatment`:**
- `has_prescription`: `Boolean`, `default=False`
- `medications`: `JSON` (array de objetos `{name, concentration, form, quantity, dosage, duration}`) — sigue el patrón ya establecido en este codebase de columnas JSON para datos clínicos estructurados-pero-flexibles (`Patient.medical_history`, `Patient.odontogram`), en vez de una tabla relacional nueva.
- `prescription_notes`: `Text` — "Indicaciones generales"
- `prescriptions` (existente) se conserva intacta, de solo lectura para atenciones creadas antes de esta feature (fallback en el detalle si `medications` está vacío).

**`backend/app/models/clinic.py` — `Clinic`:**
- `address`: `String(255)`
- `phone`: `String(50)`
- `logo_url`: `String(500)` — URL de texto plano a una imagen ya alojada externamente. **No hay subida de archivo** (decisión explícita: no se reutiliza el patrón de Supabase Storage de FCLI-10 para esto).

**Migración:** una migración Alembic (`flask db migrate` + edición manual si autogenerate no captura bien los defaults). No requiere cambios en `_scoped_models()`/RLS — ambas tablas ya tienen `clinic_id` y ya están en las dos capas de tenencia.

### 2. Backend

- `Treatment.to_dict()` expone `has_prescription`, `medications`, `prescription_notes`.
- `Clinic.to_dict()` expone `address`, `phone`, `logo_url`.
- `POST /api/treatments` y `PUT /api/treatments/<id>` (`backend/app/routes/treatments.py`) aceptan y persisten los tres campos nuevos. Validación: cada medicamento en `medications` requiere `name` y `dosage` no vacíos (rechazar con 400 si falta alguno). `update_treatment` sigue bajo `doctor_or_admin_required` (sin cambios en el decorador).
- `PUT /api/platform/clinics/<id>` (`backend/app/routes/platform_admin.py`) acepta `address`, `phone`, `logo_url` junto a los campos que ya edita.
- **Endpoint nuevo:** `GET /api/clinic/info` (blueprint accesible desde `frontend/`, no `admin-frontend`), gateado con `clinical_access_required`, automáticamente filtrado por `g.clinic_id` vía la tenencia existente (ningún parámetro de clínica en la URL). Devuelve únicamente `{name, address, phone, logo_url}` — no expone campos de suscripción/facturación, que son exclusivos de `/api/platform/*`.

### 3. Frontend (`frontend/`) — editor y detalle

**`treatment-form.component`** (aplica automáticamente a la página ruteada y al modal embebido en `patient-detail.component.html` — sin `@Input()` nuevos):
- La tarjeta "Recetario / Prescripción" reemplaza el `<textarea>` actual de "Prescripciones / Medicamentos". Header con switch "¿Con receta?".
- Con el switch activo: `FormArray` de medicamentos, cada uno una sub-tarjeta numerada con:
  - Medicamento (texto)
  - Concentración (texto)
  - Forma: `<select>` con lista fija — Comprimido, Cápsula, Jarabe, Gotas, Inyectable, Crema/Ungüento, Enjuague bucal, Otro. Si se selecciona "Otro", aparece un input de texto libre para especificar la forma.
  - Cantidad (numérico)
  - Dosis (texto)
  - Duración (texto)
  - Botón "Eliminar" por medicamento
- Botón "Agregar medicamento" al pie del `FormArray`.
- Campo "Indicaciones generales" (`prescription_notes`) debajo del `FormArray`.
- Validación de envío: no se puede guardar un medicamento sin nombre ni dosis (mismo criterio que el backend).
- Con el switch en "Sin receta": el `FormArray` no se muestra y se envía `has_prescription: false`, `medications: []`.

**`treatment-detail.component`** (página ruteada y modal embebido):
- Reemplaza el bloque "💊 Prescripciones" (párrafo plano) por una lista estructurada de medicamentos.
- Fallback: si `medications` está vacío pero `prescriptions` (legacy) tiene contenido, se muestra el texto legacy tal cual (atenciones antiguas siguen funcionando sin errores).
- Botón "Imprimir receta", visible solo si `has_prescription` es `true`. Abre `/treatments/:id/receta` con `window.open(url, '_blank')` — **no** navegación de ruta, para que funcione igual embebido y para que la impresión no incluya el resto de la app.

### 4. Frontend (`frontend/`) — vista imprimible nueva

- Nueva ruta en `frontend/src/app/features/treatments/treatments.routes.ts`: `:id/receta` → componente nuevo `TreatmentRecetaComponent`, hermano de la ruta `:id/edit` existente.
- **Autocontenido a propósito:** no es `embedded`, no recibe `@Input()` de ningún padre — evita el gotcha ya documentado en `CLAUDE.md` de `withComponentInputBinding()` para componentes ruteados-y-embebidos (`treatment-form`/`treatment-detail` ya viven expuestos a ese riesgo latente; esta feature no lo agrava agregando un tercer `@Input()`).
- Mismo `roleGuard`/`data: { pageKey: 'treatments' }` que la ruta `:id` de ver detalle (no el más estricto de `:id/edit`) — ver una receta impresa requiere el mismo permiso que ver el detalle de la atención, no el de editarla.
- El componente resuelve sus propios datos a partir del `id` de la ruta, en paralelo:
  - `TreatmentService.getById(id)` — procedimiento, medicamentos, `prescription_notes`, `doctor_name`, `doctor_id`.
  - `PatientService.getById(treatment.patient_id)` — nombre completo, `document_number` (C.I.), edad calculada desde `date_of_birth`.
  - `Treatment.to_dict()` solo expone `doctor_name`, no `specialty` — no hay que agregar un endpoint nuevo para esto: `UserService.getDoctors()` (ya existente, ya usado en `appointment-form.component.ts` con el mismo propósito) devuelve todos los doctores con su `specialty`; el componente filtra por `treatment.doctor_id` para obtener la especialidad. Línea de firma final: **`full_name` + `specialty` únicamente** (sin `license_number`, decisión explícita del usuario).
  - `GET /api/clinic/info` (nuevo, sección 2) — nombre, dirección, teléfono, logo de la clínica.
- Layout impreso (`@media print`, sin librería de generación de PDF):
  - Encabezado: logo (si `logo_url` existe), nombre de la clínica, dirección, teléfono.
  - Datos del paciente: nombre, edad, C.I.
  - Bloque ℞: cada medicamento con sus campos.
  - Indicaciones generales (`prescription_notes`).
  - Línea de firma: nombre del médico + especialidad.
  - `@page { size: auto; margin: ... }` — no hay selector de tamaño de página propio (A4 vs A5); se deja que el navegador/usuario elija al imprimir.

### 5. Frontend (`admin-frontend/`) — edición de datos de clínica

- `admin-frontend/src/app/features/clinics/clinic-detail.component.ts`/`.html`: se agregan `address`, `phone`, `logo_url` al `editForm` existente (mismo patrón `ngModel` + toggle Ver/Editar que ya tiene el resto de campos), junto a `name`, `is_active`, etc.
- `admin-frontend/src/app/core/models/index.ts`: se agregan los tres campos a la interfaz `Clinic`/`ClinicDetail`.
- `admin-frontend`'s `PlatformService` (o el servicio que llama a `PUT /api/platform/clinics/<id>`): sin cambios de firma, solo se agregan los campos nuevos al payload que ya arma `saveEdit()`.

### 6. Decisiones no cubiertas explícitamente por el ticket de Jira

- **Logo:** URL de texto, no subida de archivo (el ticket dice `String(500)`, compatible con ambas lecturas; se eligió la más simple).
- **Catálogo de "Forma":** lista fija en el frontend con opción "Otro" → texto libre, no una tabla nueva en BD (el ticket no especifica cómo se puebla el `[select]`).
- **`GET /api/clinic/info`:** endpoint completamente nuevo, no mencionado en el ticket — sin él, ningún usuario no-platform-admin del lado `frontend/` podría leer `address`/`phone`/`logo_url` de su propia clínica para el encabezado impreso.
- **Firma del médico:** el ticket original pedía "nombre, especialidad, matrícula"; el usuario pidió explícitamente quitar `matrícula` (`license_number`) — queda solo nombre + especialidad.

## Fuera de alcance

- Catálogo/autocompletado de medicamentos (más allá del `[select]` fijo de "Forma").
- Firma digital / validez legal electrónica.
- Sección de historial de recetas del paciente.
- Página de auto-configuración de clínica en `frontend/` (se edita únicamente desde `admin-frontend`).
- Selector de tamaño de página (A4/A5) en la vista imprimible — se delega al navegador.
- Subida de archivo para el logo de la clínica.

## Testing / verificación

Sin suite de tests automatizada en este repo (backend ni frontend) — verificar manualmente, en AMBOS contextos de `treatment-form`/`treatment-detail` (página ruteada y modal embebido en la ficha del paciente):
1. Con el switch en "Sin receta", el editor no se muestra y la atención se guarda sin prescripción.
2. Con el switch en "Con receta", agregar/eliminar múltiples medicamentos; confirmar que no se puede guardar uno sin nombre ni dosis (ni en frontend ni bypasseando a la API directamente).
3. Los medicamentos e indicaciones generales persisten y se ven correctamente al reabrir la atención, en ambos contextos.
4. El detalle muestra los medicamentos como lista estructurada; una atención vieja con solo `prescriptions` (legacy) se sigue mostrando sin errores.
5. El botón "Imprimir receta" abre `/treatments/:id/receta` en pestaña nueva con encabezado de clínica (incluyendo logo si está configurado), datos del paciente, medicamentos, indicaciones y firma (nombre + especialidad, sin matrícula); imprimir/guardar como PDF desde el navegador produce una salida limpia sin el resto de la app.
6. El admin edita dirección, teléfono y logo desde `admin-frontend` → `clinics` y esos datos aparecen correctamente en la vista impresa.
7. Un usuario clínico no-platform-admin puede leer `GET /api/clinic/info` de su propia clínica; confirmar que NO puede leer `/api/platform/clinics/<id>` (debe seguir dando 403, sin cambios de ese lado).
