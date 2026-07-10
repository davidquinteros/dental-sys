# Mejoras al recetario (FCLI-11 follow-up) — Diseño

**Fecha:** 2026-07-09
**Rama:** `develop`
**Alcance:** Entrega 1 de 2. La página de perfil de clínica self-service (Entrega 2) es un spec aparte.

## Contexto

El recetario estructurado (FCLI-11) ya existe: `Treatment.medications` es una columna
JSON (`[{name, concentration, form, quantity, dosage, duration}]`), el formulario de
carga está en `treatment-form.component`, y la vista imprimible en
`treatment-receta.component`. La cabecera imprimible toma nombre/dirección/teléfono/logo
de la clínica vía `GET /api/clinic/info`.

El usuario pidió tres grupos de cambios:

1. En el **formulario de medicamentos**: duración seleccionable (1 a 7 días + "Otro" →
   texto libre) y un nuevo campo de **indicaciones** por medicamento.
2. En el **recetario imprimible**: rediseño de cabecera (logo de la clínica a la
   izquierda, logo **My Dental Sys** a la derecha, información centrada, con **email**
   de contacto agregado), medicamentos **numerados**, e indicaciones del medicamento
   debajo de su detalle.

## Decisiones tomadas

- **Email de la clínica**: se agrega una columna nueva `Clinic.email`, editable **de
  momento desde admin-frontend** (mismo patrón que `address`/`phone`). La edición
  self-service por la propia clínica queda para la Entrega 2.
- **Logo My Dental Sys**: el usuario provee un archivo de imagen; se coloca bajo
  `frontend/src/assets/` y se referencia estáticamente. Hasta recibirlo, el `<img>`
  apunta a la ruta prevista y se ajusta al integrarlo.
- **Indicaciones en impresión**: línea con etiqueta — `Indicaciones: <texto>` en
  cursiva/gris, debajo del detalle de cada medicamento.
- **`indications` en el modelo de medicamento**: clave opcional dentro del JSON
  `medications`. **No requiere migración** (columna JSON libre) y
  `_validate_medications` no cambia (sigue exigiendo solo `name` + `dosage`).

## Cambios por capa

### Backend

1. **`app/models/clinic.py`**
   - Nueva columna `email = db.Column(db.String(255), nullable=True)` junto a
     `address`/`phone`/`logo_url`.
   - Agregar `"email": self.email` en `to_dict()`.

2. **Migración Alembic** (`flask db migrate` + revisión manual)
   - `ADD COLUMN email VARCHAR(255)` en `clinics`. Nullable, sin default.
   - Requiere `flask db upgrade` manual en testing y prod al desplegar (ver notas de
     deployment: Render no migra automáticamente; usar el rol de migraciones).

3. **`app/routes/clinic.py` → `clinic_info()`**
   - Agregar `"email": clinic.email` al dict de respuesta. Actualizar el docstring
     Swagger.

4. **`app/routes/platform_admin.py` → `update_clinic()`**
   - Agregar bloque `if "email" in data: clinic.email = data["email"]` junto a
     `address`/`phone`. Actualizar el docstring Swagger.

5. **`medications` (sin cambios de esquema)**
   - `_validate_medications` permanece igual. La clave `indications` viaja libre
     dentro de cada dict de medicamento y se persiste tal cual en el JSON.

### admin-frontend

1. **Modelo `Clinic`** (`admin-frontend/src/app/core/models/index.ts`)
   - Agregar `email?: string | null`.

2. **`clinic-detail.component.ts`**
   - Agregar `email: ''` a `editForm`.
   - Poblarlo en la carga: `email: d.clinic.email || ''`.
   - Ya se spread-ea en el payload del PUT (`...this.editForm`), sin cambios extra.

3. **`clinic-detail.component.html`**
   - Nuevo campo email en el formulario ver/editar, junto a dirección/teléfono
     (input en modo Editar, texto en modo Ver).

### frontend (recetario)

1. **Modelos** (`frontend/src/app/core/models/index.ts`)
   - `Medication`: agregar `indications?: string`.
   - `ClinicInfo`: agregar `email?: string`.

2. **`treatment-form.component.ts`**
   - Nueva lista `durationOptions = ['1 día','2 días','3 días','4 días','5 días','6 días','7 días','Otro']`.
   - `newMedicationGroup()`: detectar `isOtherDuration` con el mismo patrón que `form`
     (si la duración guardada no está entre los presets sin "Otro", es "Otro" + custom).
     Nuevos controles: `duration` (select), `duration_custom` (texto), `indications`
     (texto).
   - Mapeo al guardar (bloque `medications.controls.map`):
     - `duration: g.duration === 'Otro' ? (g.duration_custom || null) : (g.duration || null)`
     - `indications: g.indications || null`

3. **`treatment-form.component.html`** (tarjeta de medicamento, ~líneas 196–240)
   - Reemplazar el input de `duration` por un `<select formControlName="duration">` con
     `durationOptions`, y un input `duration_custom` visible solo cuando
     `med.get('duration')?.value === 'Otro'` (mismo condicional que `form`/`form_custom`).
   - Nuevo input de texto **Indicaciones** (`formControlName="indications"`,
     placeholder p.ej. "Ej: Tomar con alimentos").

4. **`treatment-receta.component.html`** (cabecera + medicamentos)
   - Cabecera de tres zonas: logo clínica (izq.) · bloque centrado nombre/dirección/
     teléfono/email · logo My Dental Sys (der.).
   - Mostrar email: `@if (clinic()!.email) { <p>{{ clinic()!.email }}</p> }`.
   - Medicamentos numerados: usar el índice del `@for` para el prefijo "N." antes del
     nombre.
   - Debajo del `med-detail`, si `med.indications`:
     `<p class="med-indications"><em>Indicaciones: {{ med.indications }}</em></p>`.

5. **`treatment-receta.component.css`**
   - Layout de cabecera en tres columnas (flex: logo izq., info centrada, logo der.),
     que colapse limpio en impresión. Estilo `.med-indications` (gris/cursiva) y el
     número del medicamento.

6. **Asset** `frontend/src/assets/mydentalsys-logo.<ext>`
   - Imagen provista por el usuario; referenciada en la cabecera imprimible.

## Compatibilidad hacia atrás

- Recetas existentes sin `indications` → la línea simplemente no se renderiza.
- Duraciones libres previas (p.ej. "5 dias", "10 días") → al editar, caen en "Otro" +
  custom vía la detección `isOtherDuration`; en impresión se muestran igual que hoy.
- Clínicas sin `email` → la línea de email no se renderiza; el PUT no lo exige.

## Verificación

Verificación real en navegador (Puppeteer dentro del contenedor `frontend`, por las
reglas del proyecto — no "code review"):

1. Cargar/editar una atención con receta: la duración se elige del dropdown; "Otro"
   habilita el texto; las indicaciones por medicamento se guardan y reaparecen al
   editar.
2. Editar el email de una clínica desde admin-frontend y verlo persistido tras recargar.
3. Abrir el recetario imprimible: cabecera con ambos logos e info centrada + email;
   medicamentos numerados; indicaciones bajo cada uno; vista de impresión (`window.print`)
   correcta.

## Fuera de alcance (Entrega 2)

Página de perfil de clínica self-service en `frontend/`: rutas self-scoped
(`PUT /api/clinic/info` + subida de logo) gated a admin de la clínica, nueva página con
guard/sidebar/permiso. Spec propio.
