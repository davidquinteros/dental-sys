# Impresión de Historia Médica del Paciente (FCLI-15) — Design Spec

**Fecha:** 2026-07-09
**Estado:** Aprobado
**Jira:** [FCLI-15](https://dentalsys.atlassian.net/browse/FCLI-15) — Impresión de historia médica del paciente (respaldo médico / clínica)

## Contexto

Hoy la pestaña "Historia Médica" de la ficha del paciente (`medical-history.component`, modo `readonly`) muestra los antecedentes en pantalla pero no permite imprimirlos ni respaldarlos. Esta feature agrega un botón que genera un documento imprimible con el mismo formato del recetario (FCLI-11): mismo encabezado de clínica, misma hoja de estilos de impresión.

El diseño UI/UX ya está aprobado externamente (maqueta interactiva revisada, referenciada en el ticket de Jira). Este documento formaliza las decisiones técnicas tomadas durante el brainstorming — principalmente cómo extraer el layout de impresión del recetario a algo reutilizable, y cómo renderizar el odontograma como SVG estático sin duplicar su configuración de colores/numeración.

**Dependencias ya satisfechas:** `Clinic.address`/`phone`/`logo_url` (introducidos en FCLI-11) ya están en producción. Esta historia no requiere migración de modelo propia — consume datos existentes (`Patient`, `medical_history` JSON, `odontogram` JSON, atenciones del paciente, `Clinic`).

## Alcance

### 1. Layout de impresión reutilizable (extraído del recetario existente)

**Nuevo — `frontend/src/app/shared/styles/print-document.css`:**
Hoja de estilos compartida con las reglas `@page`, `@media print` (`.no-print { display: none }`, `padding: 0`), tipografía base y spacing comunes a cualquier documento imprimible. Se importa desde el CSS de cada componente de vista imprimible (Angular soporta `styleUrls` con múltiples archivos).

**Nuevo — `frontend/src/app/shared/components/print-clinic-header/print-clinic-header.component.ts`:**
Componente standalone `<app-print-clinic-header [clinic]="clinic" [documentTitle]="'HISTORIA MÉDICA'" [issuedDate]="formattedDate">`. Renderiza logo (si existe), nombre, dirección, teléfono de la clínica, más el título del documento y la fecha de emisión. Reemplaza el header actualmente hardcodeado en `treatment-receta.component.html`.

**Refactor de `treatment-receta.component` (recetario, FCLI-11):**
Se reemplaza su bloque `<header class="receta-header">` por `<app-print-clinic-header>` y se elimina el CSS duplicado del header, importando `print-document.css` en su lugar. Sin cambios de comportamiento visible — es la extracción que pide el ticket para no duplicar layout entre recetario e historia médica.

### 2. Odontograma estático (nuevo componente presentacional)

El ticket exige explícitamente **no** incrustar el componente interactivo (`odontogram.component.ts`) en la vista imprimible — debe ser un SVG estático sin controles de edición.

**Nuevo — `frontend/src/app/features/patients/odontogram-data.ts`:**
Extrae de `odontogram.component.ts` las constantes `STATUS_CONFIG` (paleta de 9 estados: Sano, Caries, Restauración, Corona, Extraído, Endodoncia, Implante, Fractura, Ausente), los arrays de cuadrantes FDI `Q1`/`Q2`/`Q3`/`Q4` y el diccionario de nombres de dientes. `odontogram.component.ts` pasa a importar desde aquí en vez de definirlas localmente, para que el componente interactivo y el nuevo estático no puedan divergir en colores o numeración.

**Nuevo — `frontend/src/app/features/patients/odontogram-print.component.ts/html/css`:**
Componente presentacional puro: `@Input() odontogram: Record<string, {status, notes}>`. Renderiza la leyenda de colores y la grilla de 4 cuadrantes (misma estructura visual que `odontogram.component.html`: polígonos SVG por diente, X roja para extraídos), sin manejadores de click, sin panel de edición, sin llamada propia a `PatientService` (recibe los datos ya cargados por el padre). Un odontograma vacío (`{}`) renderiza todos los dientes en estado "Sano" — mismo fallback que ya usa el componente interactivo hoy (`getToothData` con default `healthy`).

### 3. Página imprimible nueva

**Nuevo — `frontend/src/app/features/patients/patient-medical-history-print.component.ts/html/css`:**

Carga en `ngOnInit` (mismo patrón que `treatment-receta.component.ts`, con `forkJoin`):

| Dato | Fuente |
|---|---|
| Paciente (info personal + `medical_history`) | `PatientService.getById(id)` |
| Odontograma | `PatientService.getOdontogram(id)` |
| Atenciones, más recientes primero | `TreatmentService.getAll({ patient_id: id, all: true })`, ordenadas client-side por `performed_at` desc |
| Clínica (header) | `ClinicService.getInfo()` |
| Firma del médico | `AuthService.currentUser()?.full_name` (síncrono) |

Contenido del documento, en el orden fijado por el ticket:

1. `<app-print-clinic-header>` con título "HISTORIA MÉDICA".
2. Información personal del paciente: nombre, CI, edad, teléfono, dirección, ciudad, teléfono de emergencia, correo, tipo de sangre, alergias (resaltadas con clase CSS distinta). Cada campo se oculta con `@if` cuando está vacío — no se imprime la etiqueta sin dato.
3–5. `<app-medical-history [value]="patient.medical_history" [readonly]="true">` — reutiliza el componente existente tal cual; ya cubre los 3 bloques (patológicos, extracciones previas, no patológicos) y ya muestra "Sin antecedentes médicos registrados" cuando no hay datos.
6. `<app-odontogram-print [odontogram]="odontogram">`.
7. Tabla de atenciones (fecha, procedimiento, pieza, diagnóstico, médico). Fila "Sin atenciones registradas" si la lista está vacía.
8. Pie con línea de firma del paciente y línea de firma del médico (solo nombre, sin especialidad ni matrícula).

Botón "Imprimir" visible en pantalla (`.no-print`), llama `window.print()` — igual que `treatment-receta.component.ts`.

### 4. Ruta

**`frontend/src/app/app.routes.ts`** — ruta top-level (fuera del shell de `LayoutComponent`), mismo patrón que `treatments/:id/receta`:

```ts
{
  path: 'patients/:id/historia/imprimir',
  loadComponent: () => import('./features/patients/patient-medical-history-print.component').then(m => m.PatientMedicalHistoryPrintComponent),
  canActivate: [roleGuard],
  data: { pageKey: 'patients' },
}
```

Fuera del shell para que `@media print` no imprima el resto de la aplicación (mismo motivo por el que `treatments/:id/receta` se movió fuera del shell — ver commit `35d765d`).

### 5. Integración — botón en la ficha del paciente

**`frontend/src/app/features/patients/patient-detail.component.html`**, pestaña "Historia Médica" (`activeTab() === 'notes'`): se agrega un `<div class="tab-section-header">` arriba de `<app-medical-history>` con el título "Historia Médica" y un botón azul con ícono de impresora (mismo estilo que "Imprimir receta" en `treatment-detail.component.ts`).

**`patient-detail.component.ts`** — nuevo método:
```ts
printMedicalHistory(): void {
  window.open(`/patients/${this.patient()!.id}/historia/imprimir`, '_blank');
}
```

## Casos límite

Todos cubiertos por diseño, sin lógica especial adicional:
- Sin antecedentes → `<app-medical-history readonly>` ya muestra "Sin antecedentes médicos registrados".
- Sin odontograma → `odontogram-print` renderiza la grilla completa en estado "Sano" (mismo comportamiento que hoy tiene el componente interactivo).
- Sin atenciones → tabla muestra fila "Sin atenciones registradas".
- Campos de paciente vacíos (dirección, ciudad, tel. emergencia, correo, alergias) → ocultos con `@if`, sin etiqueta vacía.

## Fuera de alcance (confirmado con el ticket)

- Exportación directa a PDF vía librería en backend (se usa `window.print()` nativo del navegador).
- Historial de versiones / auditoría de impresiones.
- Personalización del contenido a imprimir (selección de secciones).
- Edición de datos desde la vista imprimible (solo lectura).
- Cambios de modelo o migraciones — no se requieren.

## Verificación (Definición de Hecho del ticket)

Verificación manual en la UI con tres escenarios:
1. Paciente con datos completos (antecedentes, odontograma con estados variados, atenciones).
2. Paciente con datos parciales (campos de contacto vacíos → confirmando que se ocultan).
3. Paciente sin antecedentes / sin odontograma / sin atenciones (confirmando que no hay errores y se muestran los textos de "sin registros" correspondientes).

Impresión probada vía vista previa de impresión del navegador / guardar como PDF, confirmando salida legible en una o varias páginas.
