# Presupuesto desacoplado del Plan de Pago — cobro por ítem — Diseño

**Fecha:** 2026-07-16
**Rama:** `analisis_mejoras`
**Estado:** diseño cerrado, **sin implementar**. Próximo paso: cargar los tickets FCLI-16→28 en Jira.
**Maqueta navegable:** `2026-07-16-presupuesto-desacoplado-maqueta.html` (en esta misma carpeta — abrir con doble click)
También publicada en https://claude.ai/code/artifact/2169e911-dbd8-41c4-ae65-d07fb57faf8f

## Contexto

Hoy el flujo obliga a que todo presupuesto termine en un **plan de pago**, y ese plan cobra contra una *escalera de citas abstracta*: N citas × costo fijo, sin ninguna relación con los tratamientos reales ni con las citas de la agenda. Si el paciente hace 2 de los 5 tratamientos presupuestados, el sistema no lo sabe: sólo sabe cuántas "cuotas" entraron.

Se quiere que el presupuesto viva solo: el paciente se lleva su presupuesto, al aceptarlo se le crea el plan de tratamiento automáticamente, y va haciendo los tratamientos **por citas independientes según sus necesidades y posibilidades**. Cada pago cubre **ítems concretos del presupuesto**, y en ese momento se pueden sumar ítems adicionales (productos u otros servicios fuera del presupuesto inicial).

Resultado esperado: el presupuesto pasa de ser *un cronograma de financiación* a ser **la propuesta clínica y el tablero de avance del cobro**; la financiación en cuotas queda como una opción marcada con un check.

**Hallazgo que abarata todo el epic:** el esquema ya soporta el presupuesto suelto — `budgets.treatment_plan_id` y `budgets.converted_plan_id` son *nullable*. Lo que ata el presupuesto al plan de pago es el **flujo de UI**, no la base de datos.

## Decisiones tomadas

| # | Decisión | Consecuencia |
|---|---|---|
| 1 | **El pago se registra como Comprobante** (`Invoice`), no como ledger nuevo | 2 columnas nuevas; hereda efectivo/QR, pago parcial, anulación; `GET /billing/summary` sigue sumando solo |
| 2 | **Cobro en dos pasos**: elegir ítems → comprobante → registrar pago | Reusa el panel de pago existente; permite cobrar hoy y pagar el viernes |
| 3 | El presupuesto gana **doctor + tipo de tratamiento + pieza**; el tipo por defecto es **"Atención General"**, editable después | Alimenta el `TreatmentPlan` auto-creado |
| 4 | La **financiación es opt-in por checkbox**. Sin check: citas/período/cuotas quedan NULL y **no se imprimen** | `num_citas`/`cost_per_cita`/`down_payment` pasan a nullable |
| 5 | Doctores acceden a presupuestos **abriendo "Cobros" desde `/permissions`** | **Cero código** — ver hallazgo 🔴 abajo |
| 6 | Un presupuesto sin financiar **se puede financiar después**, mientras no se haya cobrado nada | Reusa `link-plan`; se bloquea al emitir el 1er comprobante |

**Principio rector:** el presupuesto es un **tablero de avance, no una segunda caja**. La plata sigue viviendo en los comprobantes. Los importes del presupuesto son *valor de ítems a precio de presupuesto*, no dinero recibido → las etiquetas dicen **"En ítems pagados"**, nunca "Cobrado".

## 🔴 Dos bugs encontrados de paso (verificados contra la base, no teóricos)

**1. `seed_pages()` siembra TODO en `false` — cada clínica nueva nace sin permisos.**
`backend/app/utils/seeder.py:214` compara `role.value` (`'admin'`, minúscula) contra `default_viewers` (`['ADMIN','RECEPTIONIST']`, mayúscula) → siempre `False`. Lo mismo en `can_delete` (`:222`). Verificado en la base local recién sembrada:

```
     role     |  page_key  | can_view | can_create | can_delete
 RECEPTIONIST | billing    | f        | f          | f      ← debería ser can_view=t
 DOCTOR       | treatments | f        | f          | f      ← debería ser can_view=t
```

Los admins no lo notan porque `GET /permissions/me` los trata aparte. **Toda clínica creada con `flask create-clinic` tiene a su personal no-admin sin acceso a nada** hasta que un admin tilde la matriz a mano. Fix: `role.name in viewers`.

**2. `roles:` en las rutas es configuración muerta — CLAUDE.md documenta lo contrario.**
`frontend/src/app/core/guards/auth.guard.ts:33-37`: si la ruta tiene `pageKey`, el guard **siempre retorna dentro de ese bloque** y nunca llega a leer `route.data['roles']`. Afecta a `/billing`, `users`, `permissions`, `appointment_types`, `consultorios` — los cinco declaran un `roles` que no se evalúa. CLAUDE.md lo describe como *"an extra hard gate on top of the page-permission check"*: es falso. Sólo funciona en `treatments.routes.ts:20`, que no tiene `pageKey`.

No es una fuga de datos (el backend sigue con `admin_required`), pero es una invariante documentada que no existe. **Es la razón por la que la decisión #5 no cuesta código**: a los doctores los bloquea el permiso de página, configurable desde la UI.

## Modelo de datos

Una sola migración (`down_revision = 'd8e1f4a7b920'`). Todo es ALTER: **no hace falta tocar RLS ni `_scoped_models()`** — las 4 tablas ya tienen su política `clinic_isolation`, que es a nivel tabla y no se ve afectada por columnas nuevas. Dejarlo escrito en un comentario de la migración para que nadie "arregle" una política ausente.

| Tabla | Columna | Tipo | Null |
|---|---|---|---|
| `invoice_items` | `budget_item_id` | FK → `budget_items.id` | SÍ — **NULL = ítem adicional** |
| `invoices` | `budget_id` | FK → `budgets.id`, indexado | SÍ — NULL = comprobante suelto |
| `budgets` | `doctor_id` | FK → `users.id` | SÍ en DB, requerido por la ruta |
| `budgets` | `treatment_type` | String(100) | NO, `server_default='general'` |
| `budgets` | `tooth_number` | String(20) | SÍ |
| `budgets` | `use_payment_plan` | Boolean | NO, `server_default=false` |
| `budgets` | `num_citas`, `cost_per_cita`, `down_payment` | — | **pasan de NOT NULL a nullable** |

`budgets.total_amount` **sigue NOT NULL** — el form siempre lo deriva del subtotal de ítems.

**Backfill:** `use_payment_plan = true` para todos los presupuestos existentes (todos nacieron del form con financiación obligatoria); `treatment_type`/`doctor_id` copiados del `treatment_plan` vinculado cuando exista, para que un presupuesto viejo de Ortodoncia no diga "Atención General".

**⚠️ Trampa de tenancy (la importante):** Postgres **no aplica RLS a los chequeos de foreign key**, y el filtro ORM sólo alcanza a los SELECT. Un `budget_item_id` de otra clínica pasa el FK sin problema. → **Todo `budget_item_id`/`budget_id` que venga del cliente debe resolverse con una query ORM scopeada antes de asignarse.** Nunca `setattr` de un FK crudo. Es la regla que `link_budget_plan` ya sigue.

### Estado del ítem: derivado, nunca almacenado

```
sin línea de comprobante (o sólo anuladas) → Pendiente
línea en comprobante pending/partial       → En cobro
línea en comprobante paid                  → Pagado
```

Derivarlo (no guardarlo) hace que **anular un comprobante devuelva sus ítems a Pendiente automáticamente**, sin código de compensación. Una única función `active_invoice_line()` sirve tanto al display como al guard de doble-cobro, para que no puedan discrepar.

## Flujo completo

```
  Doctor examina  →  Presupuesto (draft)          [ítems + médico + tipo]
                          │
                     Aceptar  ──────────► TreatmentPlan creado automáticamente
                          │                (misma transacción, row lock)
                          ▼
                  Presupuesto (accepted)
                          │
            ┌─────────────┴──────────────┐
     sin financiar                  financiado (check)
            │                            │
            ▼                            ▼
   Citas independientes           Crear Plan de Pago
   según necesidad/bolsillo       (escalera de cuotas, como hoy)
            │
   Cita → Cobrar ítems → Comprobante → Pago (efectivo/QR, total o parcial)
            │                                        │
            └──────── el ítem pasa a Pagado ◄────────┘
```

`Appointment.treatment_plan_id` **ya existe** → agendar citas contra el plan auto-creado funciona sin tocar nada. `Invoice.appointment_id` **ya existe** → el botón "+ Cobrar" de una cita completada ya lleva al form; sólo hay que sumarle el `budget_id`.

## Diseño de pantallas

Ver la maqueta HTML (link arriba) para el detalle visual con los componentes reales. Resumen de los cambios por pantalla:

### 1. `budget-form` — 3 tarjetas + barra de financiación colapsada

El formulario queda: **Paciente** → **Tratamiento Propuesto** → **Ítems Propuestos** → **barra de financiación**.

Tarjeta nueva **"Tratamiento Propuesto"** entre Paciente e Ítems, que absorbe `name` y `notes` (hoy viven en Condiciones): `name` arriba de todo, `doctor_id` (select, requerido), `treatment_type` (select, default "Atención General"), `tooth_number`, el `treatment_plan_id` relabelado *"Vincular a un plan existente — si lo dejás vacío se creará uno al aceptar"*, y `notes` al pie.

**La card "Condiciones" desaparece como tal**: su cuerpo se colapsa y el check **"Financiar con plan de pago" vive en su cabecera** (`.form-head` convertida en `<label>` clickeable). Sin tildar, el formulario **no muestra ni un solo campo de cuotas** — que es el caso del 90% de los presupuestos. Tildado, la misma card expande su cuerpo con el `<app-billing-conditions-fields>` existente.

**Detalles de implementación:**
- El check es un control **top-level** del FormGroup (`use_payment_plan`), no va dentro de `conditions`.
- `.form-head` tiene `border-bottom: 1px solid #f0f4f8` → colapsada, la card debe perder ese borde o queda una línea flotando bajo la nada. El `<label>` debe envolver la cabecera entera (clickeable completa, no sólo el cuadradito de 15px).
- El `@if` alrededor del componente compartido es seguro: deriva en `ngOnInit` + una suscripción con `takeUntilDestroyed`, así que destruirlo y recrearlo re-deriva limpio. **No requiere cambios en `billing-conditions-fields`.**
- Ojo: `conditions.num_citas` tiene `Validators.required` con default `3`, así que el form queda válido con la financiación apagada — pero `onSubmit` no debe *enviar* esos campos, y el backend debe **NULLear las cinco columnas cuando `use_payment_plan` es false**, sin importar qué llegue.

### 2. `budget-detail` — el cambio grande
- Fila de montos condicional: financiado → los 4 items de hoy; sin financiar → **En ítems pagados / En cobro / Pendiente / Total** + barra de avance de 3 segmentos.
- Tabla de ítems gana columna **Estado** (badge → link al comprobante).
- Tarjeta nueva **Comprobantes Generados** vía `GET /billing/invoices?budget_id=` (agregar el param a `list_invoices`, más barato que un endpoint nuevo).
- Panel de acciones — máquina de estados:

| Estado | Panel |
|---|---|
| `draft` | Aceptar *(con confirmación: avisa que se creará el plan de tratamiento)* / Rechazar |
| `accepted` + financiado + sin plan | **Crear Plan de Pago** *(hoy)* |
| `accepted` + sin financiar + queda pendiente | **Cobrar ítems** + *Financiar con plan de pago* (secundario) |
| `accepted` + sin financiar + ya hay comprobantes | **Cobrar ítems** (la opción de financiar desaparece) |
| todo pagado | badge "Presupuesto completado" *(derivado, sin enum nuevo)* |
| `converted_plan_id` / `rejected` | badges actuales |

### 3. `invoice-form` — selector de ítems
Lee `budget_id` → `getBudget()` → bloquea el paciente. Tarjeta **"Ítems del Presupuesto"** con checkboxes: los `pending` seleccionables; los demás deshabilitados mostrando su badge + link al comprobante. Los seleccionados se convierten en líneas con `budget_item_id` y descripción/cantidad/precio copiados **read-only**. Tarjeta **"Ítems Adicionales"** para los extras (`budget_item_id = null`).

**Bug a sortear:** `items: fb.array([this.newItem()])` arranca con una fila en blanco y `removeItem` no baja de 1 (`invoice-form.component.ts:36,60`) — esa fila vacía revienta contra el "Cada ítem requiere descripción y precio unitario" del backend. En modo presupuesto: arrancar **vacío**, permitir 0 extras, validar `ítems seleccionados + extras >= 1`.

### 4. `budget-print` — escalera condicional
`buildCitasRows()` retorna `[]` sin financiación. Envolver **ambos** bloques "Condiciones" y "Propuesta de Cuotas" en `@if (use_payment_plan)`; sin financiar → tabla de ítems + una línea **Total**. Agregar Médico/Tratamiento/Pieza al `patient-info`.
CLAUDE.md dice que los dos print components mantienen sus **propios** builders de citas a propósito — no refactorizar a uno compartido.

### 5. Consistencia de "Atención General"
`treatment_type` se renderiza **crudo** en 5 lugares (`treatment-plan-detail`, `patient-detail` ×2, `treatments.component`, `budget-form`, `payment-plan-form`) y el vocabulario es un `<select>` hardcodeado en `treatment-plan-form.component.html:80-90`. **Agregar un 9º valor a ese select hace que "general" se muestre como el string literal `general` en casi toda la UI.**

Extraer a `frontend/src/app/features/treatments/treatment-type-data.ts` (mismo precedente que `odontogram-data.ts`, que CLAUDE.md elogia):
```ts
export const TREATMENT_TYPES = [
  { value: 'general', label: 'Atención General' },   // ← nuevo, el default
  { value: 'endodontics', label: 'Endodoncia' }, … ] as const;
export function treatmentTypeLabel(v?: string): string { … ?? v … }
```
**Dejar `patient-detail.typeLabel()` en paz** para las filas de citas — los tipos de cita son un catálogo por clínica en la base (`AppointmentTypeCatalog`), otro vocabulario. Backend: no cambia nada, `treatment_type` es `String(100)` libre.

## Invariantes y guards

1. **Exclusividad mutua**: `POST /invoices` con `budget_id` → 400 si el presupuesto está financiado o ya convertido. `link-plan` → 400 si algún ítem ya tiene comprobante activo. No pueden competir: el flag sólo se setea en draft y el cobro requiere `accepted`.
2. **Un comprobante ↛ dos presupuestos**: estructural (`invoices.budget_id` es un FK único). Cada línea debe cumplir `item.budget_id == invoice.budget_id`.
3. **Sin doble cobro**: chequeo por `active_invoice_line()` + **row lock sobre el `Budget`** (mismo patrón que `add_payment`/`register_installment`). Un índice único parcial **no sirve**: el predicado no puede referenciar `invoices.status`, y bloquearía re-cobrar tras una anulación.
4. **`update_invoice` destruye los vínculos** — `billing.py:390-402` hace `items.clear()` y re-crea las líneas sólo con description/quantity/unit_price: cada `budget_item_id` se pierde en silencio y los ítems vuelven a "Pendiente" con el comprobante vivo. → **Se bloquea editar ítems de un comprobante con `budget_id`** ("anulá y generá uno nuevo"). El flujo agrega los extras *al momento del cobro*, así que no se pierde nada.
5. **`items.clear()` en `update_budget`** hará `DELETE` de `BudgetItem`s ya referenciados → FK violation. Hoy es inalcanzable (PUT es draft-only, el cobro requiere accepted). Comentar el FK; **no** poner `ON DELETE CASCADE`: borraría historial de facturación.
6. **Dos agujeros preexistentes a cerrar en el mismo pase**: `PUT /budgets/<id>` (`billing.py:1551`) asigna `treatment_plan_id` sin validar nada; y `create_invoice` (`billing.py:256`) usa `if not item_data.get("unit_price")`, que trata `0.00` como faltante — `create_budget` lo hace bien con `is None`.

## `accept_budget` auto-crea el plan de tratamiento

Row lock + el gate `status != DRAFT` que ya existe → el doble click cae limpio en 400. Mapeo: `doctor_id`/`treatment_type`/`tooth_number`/`name` ← del presupuesto; `total_sessions` ← `num_citas` **sólo si está financiado** (si no, NULL: un presupuesto suelto no tiene cantidad de citas por diseño); provenencia en `notes`, no volcar `budget.notes` (términos comerciales) a un campo clínico.

**Escalada de rol — deliberada y segura.** Aceptar es `clinical_access_required` (incluye recepcionista) pero `POST /treatments/plans` es `medical_staff_required`. Una recepcionista aceptando crearía un `TreatmentPlan` que no podría crear directo. Es correcto: **no autora nada clínico** — doctor, tipo y pieza los eligió quien redactó el presupuesto; aceptar sólo transcribe una propuesta ya autorizada. Restringir el accept rompería el flujo real (la recepcionista está en el mostrador cuando el paciente dice que sí).

**El salvavidas:** `doctor_id = budget.doctor_id`, requerido, **nunca `current.id`**. Ojo que `create_treatment_plan` (`treatments.py:568`) usa `data.get("doctor_id", current.id)` — copiar ese fallback acá le atribuiría el plan clínico a la recepcionista que clickeó Aceptar. Construir el modelo inline, no llamar a la ruta.

## "Editarlo luego" — dos bloqueos reales

El pedido de que el tipo se pueda cambiar después choca con dos cosas que hoy no existen:
- `PUT /treatments/plans/<id>` tiene una whitelist que **excluye `treatment_type` y `doctor_id`** (`treatments.py:669`) → el tipo de un plan creado es literalmente ineditable por API.
- **No hay ninguna UI de edición de plan de tratamiento**: no existe ruta `plans/:id/edit` y `TreatmentService.updatePlan()` (`api.service.ts:145`) no lo llama nadie.

Fix: agregar ambos campos al PUT — pero `doctor_id` **con lookup scopeado y chequeo de rol**, no un `setattr` crudo (los FK no validan `clinic_id`). Y una ruta `treatments/plans/:id/edit` reusando `treatment-plan-form` (que ya tiene el dropdown de doctores y el select de tipo; sólo le falta modo edición, espejando `budget-form.component.ts:94-123`), más un botón "Editar" en `treatment-plan-detail`.

## Tickets propuestos (FCLI-16+)

| Key | Alcance | Depende |
|---|---|---|
| **FCLI-16** | Migración + modelos: columnas nuevas, 3 a nullable, backfills, `to_dict()`. Sin RLS nueva (documentar por qué) | — |
| **FCLI-17** | Estado derivado: `active_invoice_line()`, `billing_state`, agregados del presupuesto, eager-loads | 16 |
| **FCLI-18** | API de cobro: `create_invoice` con `budget_id`+`budget_item_id` y todos los guards; bloquear edición de ítems; `list_invoices?budget_id=` | 17 |
| **FCLI-19** | `accept_budget` auto-crea el TreatmentPlan (lock, mapeo, doctor requerido); validar `treatment_plan_id` en el PUT | 16 |
| **FCLI-20** | `PUT /treatments/plans/<id>`: permitir `treatment_type` + `doctor_id` (lookup scopeado) | — |
| **FCLI-21** | `treatment-type-data.ts` + valor `general`/"Atención General"; matar los 5 sitios que renderizan el tipo crudo | — |
| **FCLI-22** | budget-form: tarjeta "Tratamiento Propuesto" + check de financiación; payload condicional; coalescer el prefill nullable en `payment-plan-form` | 16, 21 |
| **FCLI-23** | `treatments/plans/:id/edit` + modo edición + botón "Editar" en el detalle | 20, 21 |
| **FCLI-24** | budget-detail: columna Estado, agregados + barra, tarjeta Comprobantes, panel de acciones | 17, 18 |
| **FCLI-25** | invoice-form: selector de ítems del presupuesto, paciente bloqueado, validación 0 extras | 18 |
| **FCLI-26** | budget-print: escalera condicional + médico/tipo/pieza | 16, 22 |
| **FCLI-27** | 🔴 **Bugs de permisos**: casing de `seed_pages` + borrar el `roles` muerto + `billing` default_viewers += DOCTOR | — |
| **FCLI-28** | *(opcional)* `Budget.accepted_by_id`/`accepted_at`; sync CLAUDE.md + README | 19 |

**Orden sugerido**: FCLI-20/21/27 salen ya, independientes y chicos. FCLI-16 se despliega antes que todo código (la migración es aditiva y el código viejo es ciego a las columnas nuevas). Primer corte de valor: **16 → 17 → 18 → 24 → 25**. En paralelo tras 16: **19 → 22 → 23 → 26**.

**Dos párrafos de CLAUDE.md quedan falsos** al mergear FCLI-22 (el de `Budget`/`BudgetItem` y el de "Shared condiciones fields") → actualizarlos en el mismo PR, no diferir.

**Decisión #5 (doctores)**: no genera ticket de código. Es tildar `billing × doctor` en `/permissions`. Lo único a codear es el default para clínicas nuevas, que vive en FCLI-27 y **depende de arreglar el casing primero**, o no hace nada.
⚠️ Recordá que abre **todo Cobros**: el doctor pasa a ver comprobantes, planes y las tarjetas de Total Cobrado / Total Emitido de la clínica. Si algún día molesta, la salida es la página `budgets` separada (ticket grande, no incluido).

## Verificación

Sin suite de tests en el repo, así que se verifica ejercitando la API y la UI:

1. **Migración**: `DATABASE_URL="$MIGRATIONS_DATABASE_URL" flask db upgrade` y confirmar con `psql` que los backfills quedaron (`use_payment_plan=true` en los viejos) y que las 3 columnas son nullable.
2. **Presupuesto suelto**: crear uno sin financiar por `/api/docs/` → aceptar → `GET /treatments/plans?patient_id=` debe mostrar el plan auto-creado con el doctor **del presupuesto**, no el del usuario que aceptó.
3. **Doble click en Aceptar**: dos POST seguidos → el segundo debe dar 400 y debe existir **un solo** TreatmentPlan.
4. **Cobro por ítem**: comprobante con 1 ítem del presupuesto + 1 adicional → registrar pago total → `GET /billing/budgets/<id>` debe mostrar ese ítem en `paid` y el adicional sin tocar el presupuesto.
5. **Anulación devuelve el ítem**: anular ese comprobante → el ítem vuelve a `pending` y se puede volver a cobrar.
6. **Doble cobro**: intentar cobrar dos veces el mismo ítem → 400.
7. **Aislamiento**: intentar un `budget_item_id` de la Clínica Demo B desde clínica #1 → debe dar 400/404, no colarse por el FK.
8. **UI end-to-end** con Puppeteer dentro del contenedor `frontend` (receta en CLAUDE.md, incluido el flag `--host-resolver-rules`): presupuesto → aceptar → cobrar ítems → pagar → ver el estado del ítem cambiar, y el impreso sin escalera de cuotas.
