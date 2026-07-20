from flask import Blueprint, request, jsonify
from app import db
from app.models.billing import (
    Invoice, InvoiceItem, Payment, PaymentPlan, PaymentPlanInstallment,
    InvoiceStatus, PaymentMethod, PaymentPlanStatus,
    Budget, BudgetItem, BudgetStatus,
)
from app.middleware.auth import clinical_access_required, admin_required, get_current_user
from app.models.user import UserRole
from app.models.treatment import TreatmentPlan
from app.utils.clinic_time import local_now
from app.utils.scoping import resolve_scoped_doctor, resolve_scoped_treatment_plan
from datetime import datetime, date
from sqlalchemy.orm import joinedload, selectinload

billing_bp = Blueprint("billing", __name__)

# Only these are offered for new payments in this deliverable; other
# PaymentMethod members are legacy values kept for existing rows (see model).
ALLOWED_PAYMENT_METHODS = [PaymentMethod.CASH, PaymentMethod.QR]

# The whole cita ladder. An unfinanced budget (use_payment_plan=False) has all
# five NULL — see the Budget model docstring for why NULL and not 0.
FINANCING_FIELDS = ("num_citas", "cost_per_cita", "down_payment", "start_date", "end_date")


def generate_invoice_number() -> str:
    """Generate sequential invoice number like INV-2025-0001"""
    year = local_now().year
    last = Invoice.query.filter(
        Invoice.invoice_number.like(f"INV-{year}-%")
    ).order_by(Invoice.id.desc()).first()
    if last:
        seq = int(last.invoice_number.split("-")[-1]) + 1
    else:
        seq = 1
    return f"INV-{year}-{seq:04d}"


# ─── INVOICES ─────────────────────────────────────────────────────────────────

@billing_bp.route("/invoices", methods=["GET"])
@clinical_access_required
def list_invoices():
    """
    Listar facturas
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: patient_id
        type: integer
      - in: query
        name: budget_id
        type: integer
        description: Comprobantes emitidos contra un presupuesto (FCLI-17)
      - in: query
        name: status
        type: string
        enum: [pending, partial, paid, cancelled, overdue]
      - in: query
        name: page
        type: integer
        default: 1
      - in: query
        name: per_page
        type: integer
        default: 20
    responses:
      200:
        description: Lista paginada de facturas (más recientes primero)
        schema:
          type: object
          properties:
            invoices:
              type: array
              items:
                $ref: '#/definitions/Invoice'
            total:
              type: integer
            pages:
              type: integer
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    patient_id = request.args.get("patient_id", type=int)
    budget_id = request.args.get("budget_id", type=int)
    status = request.args.get("status")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # to_dict() serializes every line and reads patient/budget names — eager-load
    # them or each row costs a handful of extra queries.
    query = Invoice.query.options(
        selectinload(Invoice.items), joinedload(Invoice.patient), joinedload(Invoice.budget),
    )
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if budget_id:
        query = query.filter_by(budget_id=budget_id)
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(Invoice.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "invoices": [inv.to_dict() for inv in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
    }), 200


@billing_bp.route("/invoices/<int:invoice_id>", methods=["GET"])
@clinical_access_required
def get_invoice(invoice_id):
    """
    Obtener factura por ID
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: invoice_id
        type: integer
        required: true
    responses:
      200:
        description: Datos de la factura, incluyendo sus ítems
        schema:
          type: object
          properties:
            invoice:
              $ref: '#/definitions/Invoice'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Factura no encontrada
        schema:
          $ref: '#/definitions/Error'
    """
    invoice = Invoice.query.get_or_404(invoice_id, description="Factura no encontrada")
    return jsonify({"invoice": invoice.to_dict()}), 200


@billing_bp.route("/invoices", methods=["POST"])
@clinical_access_required
def create_invoice():
    """
    Crear factura
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Genera un número de factura secuencial (INV-{año}-{NNNN}), crea los ítems
      y calcula automáticamente subtotal, total y saldo.
      Con `budget_id` (FCLI-17) el comprobante cobra ítems concretos de un presupuesto:
      cada línea puede llevar `budget_item_id` (ítem del presupuesto) o dejarlo en null
      (ítem adicional: un producto o servicio que surgió en la cita y no estaba
      presupuestado). Ambos conviven en el mismo comprobante. El estado de cada ítem
      del presupuesto se deriva de su comprobante, no se guarda: anular este
      comprobante devuelve sus ítems a Pendiente automáticamente.
      Sólo se puede cobrar así un presupuesto **aceptado y sin financiar** — uno
      financiado se cobra por su plan de pago.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [patient_id, items]
          properties:
            patient_id:
              type: integer
              example: 3
            appointment_id:
              type: integer
              description: Cita asociada (opcional)
            budget_id:
              type: integer
              description: Presupuesto cuyos ítems se cobran (opcional)
            discount:
              type: number
              format: float
              default: 0
              example: 0
            notes:
              type: string
            due_date:
              type: string
              format: date
              example: "2026-07-01"
            items:
              type: array
              minItems: 1
              items:
                type: object
                required: [description, unit_price]
                properties:
                  description:
                    type: string
                    example: Consulta general
                  quantity:
                    type: integer
                    default: 1
                    example: 1
                  unit_price:
                    type: number
                    format: float
                    example: 150.0
                  budget_item_id:
                    type: integer
                    description: Ítem del presupuesto que cubre esta línea; null = ítem adicional
    responses:
      201:
        description: Factura creada correctamente
        schema:
          type: object
          properties:
            invoice:
              $ref: '#/definitions/Invoice'
            message:
              type: string
      400:
        description: >
          patient_id faltante, sin ítems, ítem incompleto, fecha inválida, presupuesto
          inexistente/no aceptado/financiado/ya convertido, ítem de otro presupuesto,
          o ítem ya cobrado en otro comprobante
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    data = request.get_json()

    if not data.get("patient_id"):
        return jsonify({"error": "patient_id es requerido"}), 400

    items_data = data.get("items", [])
    if not items_data:
        return jsonify({"error": "Se requiere al menos un ítem"}), 400

    for item_data in items_data:
        # `is None`, NOT falsiness: a 0.00 line (a freebie, or a budget item
        # priced at zero) is legitimate and used to be rejected here as if the
        # price were missing. create_budget already got this right.
        if not item_data.get("description") or item_data.get("unit_price") is None:
            return jsonify({"error": "Cada ítem requiere descripción y precio unitario"}), 400

    # ── Budget mode (FCLI-17) ───────────────────────────────────────────────
    budget = None
    if data.get("budget_id"):
        # Row lock, same pattern as add_payment/register_installment: two
        # simultaneous "Cobrar ítems" would otherwise both read the same item as
        # pending and each charge it. The second one waits here, then trips the
        # already-charged guard below.
        budget = (
            Budget.query.filter_by(id=data["budget_id"]).with_for_update().first()
        )
        # Scoped ORM lookup, never a raw FK assign: Postgres does not apply RLS
        # to foreign-key checks, so another clinic's budget_id would satisfy the
        # constraint silently.
        if budget is None:
            return jsonify({"error": "Presupuesto no encontrado"}), 404
        if budget.status != BudgetStatus.ACCEPTED:
            return jsonify({"error": "Solo se pueden cobrar ítems de un presupuesto aceptado"}), 400
        # Mutually exclusive with financing: a financed budget is collected
        # through its payment plan, not per item.
        if budget.use_payment_plan or budget.converted_plan_id is not None:
            return jsonify({
                "error": "Este presupuesto se cobra con su plan de pago, no por ítem"
            }), 400
        try:
            same_patient = budget.patient_id == int(data["patient_id"])
        except (TypeError, ValueError):
            return jsonify({"error": "patient_id inválido"}), 400
        if not same_patient:
            return jsonify({"error": "El presupuesto no corresponde a ese paciente"}), 400

    # Resolve every budget_item_id up front, scoped, before writing anything.
    resolved_lines = []
    seen_item_ids = set()
    for item_data in items_data:
        raw_item_id = item_data.get("budget_item_id")
        budget_item = None
        if raw_item_id is not None:
            if budget is None:
                return jsonify({
                    "error": "Un comprobante sin presupuesto no puede cobrar ítems de un presupuesto"
                }), 400
            budget_item = BudgetItem.query.filter_by(id=raw_item_id).first()
            # One comprobante never spans two budgets: the item must belong to
            # THIS budget. Covers the cross-clinic case too (the ORM filter makes
            # another clinic's item invisible → None → 400 here).
            if budget_item is None or budget_item.budget_id != budget.id:
                return jsonify({"error": "El ítem no pertenece a este presupuesto"}), 400
            # The same item can't appear twice in ONE payload: active_invoice_line()
            # only sees already-committed lines, so without this two lines with the
            # same budget_item_id would both pass and charge it twice on this very
            # comprobante (invisible on the board, which shows the item once).
            if budget_item.id in seen_item_ids:
                return jsonify({
                    "error": f"El ítem «{budget_item.description}» está repetido en el comprobante"
                }), 400
            seen_item_ids.add(budget_item.id)
            # No double charge across comprobantes. Same active_invoice_line() the
            # display uses, so what the UI greys out and what the server rejects
            # can't drift.
            existing = budget_item.active_invoice_line()
            if existing is not None:
                return jsonify({
                    "error": f"El ítem «{budget_item.description}» ya está en el comprobante "
                             f"{existing.invoice.invoice_number}"
                }), 400
        resolved_lines.append((item_data, budget_item))

    invoice = Invoice(
        clinic_id=current.clinic_id,
        invoice_number=generate_invoice_number(),
        patient_id=data["patient_id"],
        appointment_id=data.get("appointment_id"),
        budget_id=budget.id if budget else None,
        created_by_id=current.id,
        discount=data.get("discount", 0),
        notes=data.get("notes"),
    )

    if data.get("due_date"):
        try:
            invoice.due_date = date.fromisoformat(data["due_date"])
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido"}), 400

    db.session.add(invoice)
    db.session.flush()  # Get invoice.id

    for item_data, budget_item in resolved_lines:
        qty = item_data.get("quantity", 1)
        unit_price = float(item_data["unit_price"])
        item = InvoiceItem(
            clinic_id=invoice.clinic_id,
            invoice_id=invoice.id,
            budget_item_id=budget_item.id if budget_item else None,
            description=item_data["description"],
            quantity=qty,
            unit_price=unit_price,
            total=qty * unit_price,
        )
        db.session.add(item)

    db.session.flush()
    invoice.recalculate()
    db.session.commit()

    return jsonify({"invoice": invoice.to_dict(), "message": "Factura creada correctamente"}), 201


@billing_bp.route("/invoices/<int:invoice_id>", methods=["PUT"])
@clinical_access_required
def update_invoice(invoice_id):
    """
    Actualizar factura
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      No se puede modificar una factura ya pagada o cancelada. Si se envían `items`,
      reemplaza por completo los ítems existentes (solo posible mientras está pendiente).
    parameters:
      - in: path
        name: invoice_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            discount:
              type: number
              format: float
            notes:
              type: string
            status:
              type: string
              enum: [cancelled]
              description: Único valor aceptado para cambiar manualmente el estado
            items:
              type: array
              minItems: 1
              description: Reemplaza todos los ítems de la factura
              items:
                type: object
                required: [description, unit_price]
                properties:
                  description:
                    type: string
                    example: Consulta general
                  quantity:
                    type: integer
                    default: 1
                    example: 1
                  unit_price:
                    type: number
                    format: float
                    example: 150.0
    responses:
      200:
        description: Factura actualizada (recalcula totales)
        schema:
          type: object
          properties:
            invoice:
              $ref: '#/definitions/Invoice'
            message:
              type: string
      400:
        description: La factura ya está pagada o cancelada, o ítem inválido
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Factura no encontrada
        schema:
          $ref: '#/definitions/Error'
    """
    invoice = Invoice.query.get_or_404(invoice_id)

    if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]:
        return jsonify({"error": "No se puede modificar una factura pagada o cancelada"}), 400

    data = request.get_json()

    # Cancelling or replacing items only makes sense before any money has been
    # collected — once a partial payment exists, cancelling would silently drop
    # already-received Payment rows out of every revenue report (recalculate()
    # leaves CANCELLED invoices' balance/amount_paid frozen, and both are
    # excluded from GET /billing/summary and the dashboard by status).
    if (("status" in data and data["status"] == "cancelled") or "items" in data) and invoice.status != InvoiceStatus.PENDING:
        return jsonify({"error": "Solo se puede cancelar o editar los ítems de una factura pendiente (sin pagos registrados)"}), 400

    # Replacing the items of a budget-backed comprobante is blocked outright:
    # the branch below does items.clear() and rebuilds each line from
    # description/quantity/unit_price only, so every budget_item_id would be
    # dropped **in the database** — the items would silently fall back to
    # "Pendiente" while this comprobante still charges them, and could then be
    # charged a second time. Cancel and re-issue instead: nothing is lost, since
    # the extras are added at collection time anyway, and it's better accounting
    # (sequential numbering, and cancelled comprobantes are already excluded from
    # every aggregate). Deliberate scope cut — see FCLI-17.
    if "items" in data and invoice.budget_id is not None:
        return jsonify({
            "error": "No se pueden editar los ítems de un comprobante de presupuesto. "
                     "Anulá el comprobante y generá uno nuevo."
        }), 400

    if "discount" in data:
        invoice.discount = float(data["discount"])
    if "notes" in data:
        invoice.notes = data["notes"]
    if "status" in data and data["status"] == "cancelled":
        invoice.status = InvoiceStatus.CANCELLED

    if "items" in data:
        items_data = data["items"]
        if not items_data:
            return jsonify({"error": "Se requiere al menos un ítem"}), 400
        for item_data in items_data:
            # `is None`, not falsiness — a 0.00 line is legitimate (same fix as
            # create_invoice).
            if not item_data.get("description") or item_data.get("unit_price") is None:
                return jsonify({"error": "Cada ítem requiere descripción y precio unitario"}), 400

        # Mutate the relationship collection itself (not raw session.delete/add
        # with a manual invoice_id) so `invoice.items` is correct in memory —
        # recalculate() below sums that same collection right after.
        invoice.items.clear()
        db.session.flush()

        for item_data in items_data:
            qty = item_data.get("quantity", 1)
            unit_price = float(item_data["unit_price"])
            invoice.items.append(InvoiceItem(
                clinic_id=invoice.clinic_id,
                description=item_data["description"],
                quantity=qty,
                unit_price=unit_price,
                total=qty * unit_price,
            ))
        db.session.flush()

    invoice.recalculate()
    db.session.commit()
    return jsonify({"invoice": invoice.to_dict(), "message": "Factura actualizada"}), 200


# ─── PAYMENTS ─────────────────────────────────────────────────────────────────

@billing_bp.route("/invoices/<int:invoice_id>/payments", methods=["POST"])
@clinical_access_required
def add_payment(invoice_id):
    """
    Registrar pago de una factura
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Registra un abono parcial o total. Actualiza `amount_paid`, `balance` y `status`
      de la factura automáticamente (pending → partial → paid).
    parameters:
      - in: path
        name: invoice_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [amount]
          properties:
            amount:
              type: number
              format: float
              example: 150.0
              description: Debe ser positivo y no exceder el saldo pendiente
            method:
              type: string
              enum: [cash, qr]
              default: cash
              example: cash
            reference:
              type: string
              description: Referencia de transacción/tarjeta
            notes:
              type: string
    responses:
      201:
        description: Pago registrado correctamente
        schema:
          type: object
          properties:
            payment:
              $ref: '#/definitions/Payment'
            invoice:
              $ref: '#/definitions/Invoice'
            message:
              type: string
      400:
        description: Factura pagada/cancelada, monto faltante, no positivo o excede el saldo
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Factura no encontrada
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    # Row lock: without it, two concurrent payments against the same invoice
    # can both read the same pre-payment balance and both pass validation,
    # corrupting amount_paid/balance. Held until commit/rollback below.
    invoice = Invoice.query.filter_by(id=invoice_id).with_for_update().first()
    if not invoice:
        return jsonify({"error": "Factura no encontrada"}), 404

    if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]:
        return jsonify({"error": "La factura ya está pagada o cancelada"}), 400

    data = request.get_json()
    if not data.get("amount"):
        return jsonify({"error": "amount es requerido"}), 400

    amount = float(data["amount"])
    if amount <= 0:
        return jsonify({"error": "El monto debe ser positivo"}), 400

    if amount > float(invoice.balance):
        return jsonify({"error": f"El monto excede el saldo pendiente ({invoice.balance})"}), 400

    try:
        method = PaymentMethod(data.get("method", "cash"))
    except ValueError:
        method = None
    if method not in ALLOWED_PAYMENT_METHODS:
        valid = [m.value for m in ALLOWED_PAYMENT_METHODS]
        return jsonify({"error": f"Método de pago inválido. Válidos: {valid}"}), 400

    payment = Payment(
        clinic_id=invoice.clinic_id,
        invoice_id=invoice.id,
        received_by_id=current.id,
        amount=amount,
        method=method,
        reference=data.get("reference"),
        notes=data.get("notes"),
    )

    invoice.amount_paid = float(invoice.amount_paid) + amount
    invoice.recalculate()

    db.session.add(payment)
    db.session.commit()

    return jsonify({
        "payment": payment.to_dict(),
        "invoice": invoice.to_dict(),
        "message": "Pago registrado correctamente"
    }), 201


# ─── PAYMENT PLANS ─────────────────────────────────────────────────────────────

@billing_bp.route("/payment-plans", methods=["GET"])
@clinical_access_required
def list_payment_plans():
    """
    Listar planes de pago
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: patient_id
        type: integer
      - in: query
        name: status
        type: string
        enum: [active, completed, cancelled, defaulted]
    responses:
      200:
        description: Lista de planes de pago (más recientes primero)
        schema:
          type: object
          properties:
            payment_plans:
              type: array
              items:
                $ref: '#/definitions/PaymentPlan'
            total:
              type: integer
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
    """
    patient_id = request.args.get("patient_id", type=int)
    status = request.args.get("status")

    query = PaymentPlan.query
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if status:
        query = query.filter_by(status=status)

    plans = query.order_by(PaymentPlan.created_at.desc()).all()
    return jsonify({"payment_plans": [p.to_dict() for p in plans], "total": len(plans)}), 200


@billing_bp.route("/payment-plans/<int:plan_id>", methods=["GET"])
@clinical_access_required
def get_payment_plan(plan_id):
    """
    Obtener plan de pago por ID
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: plan_id
        type: integer
        required: true
    responses:
      200:
        description: Datos del plan de pago
        schema:
          type: object
          properties:
            payment_plan:
              $ref: '#/definitions/PaymentPlan'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Plan de pago no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    plan = PaymentPlan.query.get_or_404(plan_id, description="Plan de pago no encontrado")
    return jsonify({"payment_plan": plan.to_dict()}), 200


@billing_bp.route("/payment-plans", methods=["POST"])
@clinical_access_required
def create_payment_plan():
    """
    Crear plan de pago
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Asociado a un plan de tratamiento. `installments` (cantidad de citas) e
      `installment_amount` (costo fijo por cita) quedan fijos según `calc_mode`:
      en `per_cita` se envía `cost_per_cita` y el servidor calcula
      `total_amount = down_payment + num_citas * cost_per_cita`; en `total` se
      envía `total_amount` y el servidor calcula
      `cost_per_cita = (total_amount - down_payment) / num_citas`. El plan se crea
      con `total_paid = 0` (nada cobrado todavía); el enganche/cuota inicial se
      registra después como cualquier otro pago, no se marca como pagado al crear.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [patient_id, treatment_plan_id, name, num_citas, calc_mode]
          properties:
            patient_id:
              type: integer
              example: 11
            treatment_plan_id:
              type: integer
              example: 3
            name:
              type: string
              example: Plan de pago - Ortodoncia
            calc_mode:
              type: string
              enum: [per_cita, total]
              example: per_cita
            num_citas:
              type: integer
              example: 12
            cost_per_cita:
              type: number
              format: float
              description: Requerido si calc_mode=per_cita
              example: 300.0
            total_amount:
              type: number
              format: float
              description: Requerido si calc_mode=total
              example: 4500.0
            down_payment:
              type: number
              format: float
              default: 0
              example: 900.0
            start_date:
              type: string
              format: date
              example: "2026-04-15"
            end_date:
              type: string
              format: date
              example: "2027-04-15"
            notes:
              type: string
    responses:
      201:
        description: Plan de pago creado
        schema:
          type: object
          properties:
            payment_plan:
              $ref: '#/definitions/PaymentPlan'
            message:
              type: string
      400:
        description: Campo requerido faltante o fecha inválida
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    data = request.get_json()
    required = ["patient_id", "treatment_plan_id", "name", "num_citas", "calc_mode"]
    for field in required:
        if data.get(field) is None:
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    calc_mode = data["calc_mode"]
    if calc_mode not in ("per_cita", "total"):
        return jsonify({"error": "calc_mode debe ser 'per_cita' o 'total'"}), 400

    num_citas = int(data["num_citas"])
    if num_citas < 1:
        return jsonify({"error": "La cantidad de citas debe ser al menos 1"}), 400
    down = float(data.get("down_payment", 0))

    if calc_mode == "per_cita":
        if data.get("cost_per_cita") is None:
            return jsonify({"error": "Campo requerido: cost_per_cita"}), 400
        cost_per_cita = float(data["cost_per_cita"])
        total = round(down + num_citas * cost_per_cita, 2)
    else:
        if data.get("total_amount") is None:
            return jsonify({"error": "Campo requerido: total_amount"}), 400
        total = float(data["total_amount"])
        cost_per_cita = round((total - down) / num_citas, 2)

    if cost_per_cita <= 0:
        return jsonify({"error": "El costo por cita debe ser positivo"}), 400
    if total <= 0:
        return jsonify({"error": "El monto total debe ser positivo"}), 400

    start_date_val = None
    end_date_val = None
    if data.get("start_date"):
        try:
            start_date_val = date.fromisoformat(data["start_date"])
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido"}), 400
    if data.get("end_date"):
        try:
            end_date_val = date.fromisoformat(data["end_date"])
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido"}), 400
    if start_date_val and end_date_val and end_date_val < start_date_val:
        return jsonify({"error": "La fecha de fin no puede ser anterior a la fecha de inicio"}), 400

    plan = PaymentPlan(
        clinic_id=current.clinic_id,
        patient_id=data["patient_id"],
        treatment_plan_id=data["treatment_plan_id"],
        created_by_id=current.id,
        name=data["name"],
        total_amount=total,
        down_payment=down,
        installments=num_citas,
        installment_amount=cost_per_cita,
        total_paid=0,
        start_date=start_date_val,
        end_date=end_date_val,
        notes=data.get("notes"),
    )

    # A new plan is created "enabled" with nothing collected yet — total_paid starts at 0
    # and the balance includes the down_payment. The enganche is registered afterwards
    # like any other payment (POST /payment-plans/<id>/installment), not auto-marked as
    # paid here. The paid_installments/partial_progress_amount derivation subtracts
    # down_payment from total_paid, so the first `down` collected is attributed to the
    # enganche and only money beyond that advances the citas.
    db.session.add(plan)
    db.session.commit()

    return jsonify({"payment_plan": plan.to_dict(), "message": "Plan de pago creado"}), 201


@billing_bp.route("/payment-plans/<int:plan_id>", methods=["PUT"])
@clinical_access_required
def update_payment_plan(plan_id):
    """
    Actualizar plan de pago
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Solo se pueden editar planes en estado `active`. El paciente y el plan de tratamiento
      asociado no se pueden cambiar. `total_amount`, `down_payment`, `cost_per_cita` y
      `calc_mode` solo se pueden modificar mientras `paid_installments == 0` (ningún pago de
      cita registrado todavía) — una vez que hay pagos, el costo por cita queda fijo.
      `num_citas` sí se puede aumentar en cualquier momento (nunca reducir por debajo de las
      citas ya pagadas); si cambia solo la cantidad de citas, `total_amount` se recalcula
      manteniendo fijo el costo por cita.
    parameters:
      - in: path
        name: plan_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            calc_mode:
              type: string
              enum: [per_cita, total]
            num_citas:
              type: integer
            cost_per_cita:
              type: number
              format: float
            total_amount:
              type: number
              format: float
            down_payment:
              type: number
              format: float
            start_date:
              type: string
              format: date
            end_date:
              type: string
              format: date
            notes:
              type: string
    responses:
      200:
        description: Plan de pago actualizado
        schema:
          type: object
          properties:
            payment_plan:
              $ref: '#/definitions/PaymentPlan'
            message:
              type: string
      400:
        description: Plan no activo, cuotas inválidas, fecha inválida, o intento de modificar el costo por cita de un plan con pagos registrados
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Plan de pago no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    plan = PaymentPlan.query.get_or_404(plan_id, description="Plan de pago no encontrado")
    if plan.status != PaymentPlanStatus.ACTIVE:
        return jsonify({"error": "Solo se pueden editar planes de pago activos"}), 400

    data = request.get_json() or {}
    if "name" in data:
        plan.name = data["name"]
    if "notes" in data:
        plan.notes = data["notes"]
    if "start_date" in data:
        if data["start_date"]:
            try:
                plan.start_date = date.fromisoformat(data["start_date"])
            except ValueError:
                return jsonify({"error": "Formato de fecha inválido"}), 400
        else:
            plan.start_date = None
    if "end_date" in data:
        if data["end_date"]:
            try:
                plan.end_date = date.fromisoformat(data["end_date"])
            except ValueError:
                return jsonify({"error": "Formato de fecha inválido"}), 400
        else:
            plan.end_date = None
    if plan.start_date and plan.end_date and plan.end_date < plan.start_date:
        return jsonify({"error": "La fecha de fin no puede ser anterior a la fecha de inicio"}), 400

    cost_field_names = ("total_amount", "down_payment", "cost_per_cita", "calc_mode")
    cost_fields_present = any(f in data for f in cost_field_names)
    num_citas_present = "num_citas" in data or "installments" in data

    # Use total_paid > down_payment (not paid_installments > 0) as the "has this plan
    # collected any cita money yet" check — a partial payment can leave paid_installments
    # at 0 (no cita fully covered yet) while still having collected real money.
    if cost_fields_present and float(plan.total_paid) > float(plan.down_payment):
        return jsonify({"error": "No se puede modificar el costo por cita de un plan con pagos registrados"}), 400

    if num_citas_present:
        new_installments = int(data.get("num_citas", data.get("installments")))
        if new_installments < 1:
            return jsonify({"error": "La cantidad de citas debe ser al menos 1"}), 400
        if new_installments < plan.paid_installments:
            return jsonify({"error": "No se puede reducir la cantidad de citas por debajo de las ya pagadas"}), 400
        plan.installments = new_installments

    if cost_fields_present:
        # Only reachable when total_paid == down_payment, i.e. no cita money collected yet (checked above).
        down = float(data.get("down_payment", plan.down_payment))
        calc_mode = data.get("calc_mode")
        if calc_mode == "per_cita" or (calc_mode is None and "cost_per_cita" in data and "total_amount" not in data):
            cost_per_cita = float(data.get("cost_per_cita", plan.installment_amount))
            total = round(down + plan.installments * cost_per_cita, 2)
        else:
            total = float(data.get("total_amount", plan.total_amount))
            cost_per_cita = round((total - down) / plan.installments, 2)
        plan.total_amount = total
        plan.down_payment = down
        plan.installment_amount = cost_per_cita
    elif num_citas_present:
        # Citas count changed but cost per cita stays fixed — total scales accordingly.
        plan.total_amount = round(float(plan.down_payment) + plan.installments * float(plan.installment_amount), 2)

    db.session.commit()
    return jsonify({"payment_plan": plan.to_dict(), "message": "Plan de pago actualizado"}), 200


@billing_bp.route("/payment-plans/<int:plan_id>/installment", methods=["POST"])
@clinical_access_required
def register_installment(plan_id):
    """
    Registrar pago de cuota
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Registra un pago contra el plan — completo (`count`, N citas al costo fijo por cita) o
      parcial (`amount`, monto libre menor a una cuota). El costo por cita nunca se recalcula;
      `paid_installments` es un valor derivado (citas completamente cubiertas por `total_paid`,
      `floor((total_paid - down_payment) / installment_amount)`), no un contador independiente —
      un pago parcial puede dejarlo sin cambios si no alcanza a completar la próxima cita. El
      plan pasa a `completed` cuando `balance` llega a 0. Si el pago inicial (`down_payment`)
      todavía no está cubierto (`total_paid < down_payment`), un pago `count` (citas completas)
      se rechaza con 400 — el pago inicial debe registrarse primero, vía `amount`.
    parameters:
      - in: path
        name: plan_id
        type: integer
        required: true
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            count:
              type: integer
              description: "Pago completo: cantidad de citas a pagar de una vez (amount = count * installment_amount). No puede exceder el saldo pendiente."
            amount:
              type: number
              format: float
              description: "Pago parcial: monto libre, puede ser menor a una cuota. Debe ser positivo y no exceder el saldo pendiente."
            notes:
              type: string
    responses:
      200:
        description: Pago registrado
        schema:
          type: object
          properties:
            payment_plan:
              $ref: '#/definitions/PaymentPlan'
            message:
              type: string
      400:
        description: >
          El plan ya está completamente pagado, el monto/cantidad de citas es inválido,
          o se intentó un pago de citas completas (`count`) antes de cubrir el pago inicial
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Plan de pago no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    # Row lock: without it, two concurrent payments against the same plan (two staff
    # members, or a retried request) can both read the same pre-payment balance and
    # both pass validation, over-crediting total_paid beyond total_amount — same class
    # of race add_payment() already guards against for invoices.
    plan = PaymentPlan.query.filter_by(id=plan_id).with_for_update().first()
    if not plan:
        return jsonify({"error": "Plan de pago no encontrado"}), 404
    data = request.get_json() or {}

    if plan.balance <= 0:
        return jsonify({"error": "El plan ya está completamente pagado"}), 400

    down_payment_pending = float(plan.down_payment) > 0 and float(plan.total_paid) < float(plan.down_payment)

    if "count" in data:
        if down_payment_pending:
            return jsonify({"error": "Debe registrarse el pago inicial (cuota inicial) antes de pagar citas completas"}), 400
        count = int(data["count"])
        if count < 1:
            return jsonify({"error": "La cantidad de citas a pagar debe ser al menos 1"}), 400
        amount = round(count * float(plan.installment_amount), 2)
        if amount <= 0:
            return jsonify({"error": "El monto debe ser positivo"}), 400
    else:
        amount = float(data.get("amount", plan.installment_amount))
        if amount <= 0:
            return jsonify({"error": "El monto debe ser positivo"}), 400

    if amount > float(plan.balance):
        return jsonify({"error": f"El monto excede el saldo pendiente ({plan.balance})"}), 400

    plan.total_paid = float(plan.total_paid) + amount

    # paid_installments is derived from the ledger (total_paid), not incremented directly —
    # a partial payment can leave it unchanged if it doesn't fully cover the next cita.
    if plan.installment_amount:
        progress = float(plan.total_paid) - float(plan.down_payment)
        plan.paid_installments = min(plan.installments, max(0, int((progress + 1e-6) // float(plan.installment_amount))))

    db.session.add(PaymentPlanInstallment(
        clinic_id=plan.clinic_id,
        payment_plan_id=plan.id,
        received_by_id=current.id,
        amount=amount,
        notes=data.get("notes"),
        # Freeze the plan state as of this payment for the printed receipt (comprobante).
        total_paid_after=round(float(plan.total_paid), 2),
        balance_after=round(float(plan.balance), 2),
    ))

    # balance<=0 is the ONLY completion criterion (not also paid_installments>=installments)
    # — in calc_mode='total', cost_per_cita is a rounded derivative of total_amount, so
    # installments*cost_per_cita can round below total_amount (e.g. 1000/3 -> 333.33*3 =
    # 999.99). Completing on paid_installments reaching installments would silently write
    # off that rounding remainder as "paid" while balance is still positive.
    if plan.balance <= 0:
        plan.status = PaymentPlanStatus.COMPLETED

    db.session.commit()
    return jsonify({"payment_plan": plan.to_dict(), "message": "Pago registrado"}), 200


@billing_bp.route("/payment-plans/<int:plan_id>/installments", methods=["GET"])
@clinical_access_required
def list_plan_installments(plan_id):
    """
    Historial de pagos de un plan de pago
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Pagos individuales registrados contra el plan (enganche + cada cuota), del más
      reciente al más antiguo. Si `total_paid` es mayor que la suma de estos registros
      (planes creados antes de que existiera este historial), se antepone un ítem
      "Pagos registrados antes de este historial" con la diferencia, para que la suma
      siempre coincida con `total_paid`.
    parameters:
      - in: path
        name: plan_id
        type: integer
        required: true
    responses:
      200:
        description: Lista de pagos
        schema:
          type: object
          properties:
            installments:
              type: array
              items:
                $ref: '#/definitions/PaymentPlanInstallment'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Plan de pago no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    plan = PaymentPlan.query.get_or_404(plan_id, description="Plan de pago no encontrado")
    logged = PaymentPlanInstallment.query.filter_by(payment_plan_id=plan_id) \
        .order_by(PaymentPlanInstallment.payment_date.desc()).all()
    items = [p.to_dict() for p in logged]

    logged_total = sum(float(p.amount) for p in logged)
    gap = float(plan.total_paid) - logged_total
    if gap > 0.01:
        items.append({
            "id": None,
            "payment_plan_id": plan.id,
            "amount": round(gap, 2),
            "notes": "Pagos registrados antes de este historial",
            "payment_date": plan.created_at.isoformat() if plan.created_at else None,
            "received_by": None,
        })

    return jsonify({"installments": items}), 200


@billing_bp.route("/summary", methods=["GET"])
@clinical_access_required
def billing_summary():
    """
    Resumen financiero
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Totales generales de facturación (histórico completo, sin filtro de fechas).
      Las facturas canceladas no se contabilizan.
    responses:
      200:
        description: Resumen financiero general
        schema:
          type: object
          properties:
            total_invoiced:
              type: number
              format: float
              example: 117504.0
            total_collected:
              type: number
              format: float
              example: 93576.0
            pending_balance:
              type: number
              format: float
              example: 23928.0
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
    """
    from sqlalchemy import func
    total_invoiced = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.status != InvoiceStatus.CANCELLED
    ).scalar() or 0
    total_collected = db.session.query(func.sum(Invoice.amount_paid)).filter(
        Invoice.status != InvoiceStatus.CANCELLED
    ).scalar() or 0
    pending = db.session.query(func.sum(Invoice.balance)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIAL])
    ).scalar() or 0

    return jsonify({
        "total_invoiced": float(total_invoiced),
        "total_collected": float(total_collected),
        "pending_balance": float(pending),
    }), 200


# ─── PRESUPUESTOS ──────────────────────────────────────────────────────────────

@billing_bp.route("/budgets", methods=["GET"])
@clinical_access_required
def list_budgets():
    """
    Listar presupuestos
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: patient_id
        type: integer
      - in: query
        name: status
        type: string
        enum: [draft, accepted, rejected]
    responses:
      200:
        description: Lista de presupuestos (más recientes primero)
        schema:
          type: object
          properties:
            budgets:
              type: array
              items:
                $ref: '#/definitions/Budget'
            total:
              type: integer
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
    """
    patient_id = request.args.get("patient_id", type=int)
    status = request.args.get("status")

    # The aggregates read every item, and every item resolves its comprobante —
    # so without these eager loads this list is 1 + N·M queries. With them it's a
    # handful, flat, no matter how many budgets. The ORM tenancy filter uses
    # with_loader_criteria(..., include_aliases=True), which applies to eager
    # loads too, so the InvoiceItem/Invoice legs stay clinic-scoped.
    query = Budget.query.options(
        joinedload(Budget.patient), joinedload(Budget.doctor), joinedload(Budget.treatment_plan),
        selectinload(Budget.items)
        .selectinload(BudgetItem.invoice_lines)
        .joinedload(InvoiceItem.invoice),
    )
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if status:
        query = query.filter_by(status=status)

    budgets = query.order_by(Budget.created_at.desc()).all()
    # include_items=False: a card shows the aggregates, never the item array.
    # (This endpoint still ignores per_page — real pagination is out of scope.)
    return jsonify({
        "budgets": [b.to_dict(include_items=False) for b in budgets],
        "total": len(budgets),
    }), 200


@billing_bp.route("/budgets/<int:budget_id>", methods=["GET"])
@clinical_access_required
def get_budget(budget_id):
    """
    Obtener presupuesto por ID
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: budget_id
        type: integer
        required: true
    responses:
      200:
        description: Datos del presupuesto
        schema:
          type: object
          properties:
            budget:
              $ref: '#/definitions/Budget'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Presupuesto no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    # Same eager loads as list_budgets: the detail DOES serialize every item, and
    # each one resolves its comprobante for billing_state.
    budget = (
        Budget.query.options(
            selectinload(Budget.items)
            .selectinload(BudgetItem.invoice_lines)
            .joinedload(InvoiceItem.invoice)
        )
        .filter_by(id=budget_id)
        .first()
    )
    if budget is None:
        return jsonify({"error": "Presupuesto no encontrado"}), 404
    return jsonify({"budget": budget.to_dict()}), 200


@billing_bp.route("/budgets", methods=["POST"])
@clinical_access_required
def create_budget():
    """
    Crear presupuesto
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      El presupuesto es la propuesta clínica y NO obliga a un plan de pago (FCLI-16).
      La financiación es opt-in: sólo si `use_payment_plan` es true se piden (y se
      guardan) `num_citas`/`calc_mode` y el resto de la escalera de cuotas — si es
      false, `num_citas`/`cost_per_cita`/`down_payment`/`start_date`/`end_date` quedan
      NULL sin importar qué mande el cliente, y el paciente paga por ítem a medida que
      avanza.
      `doctor_id` y `treatment_type` (por defecto `general`, "Atención General") son la
      propuesta clínica: al aceptar el presupuesto se copian al plan de tratamiento que
      se crea automáticamente. `treatment_plan_id` es opcional y normalmente no existe
      todavía; si se envía, debe ser un plan del mismo paciente.
      `items` es una lista puramente descriptiva de lo observado/propuesto; no condiciona
      `total_amount` server-side (el formulario siempre lo deriva del subtotal de ítems).
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [patient_id, name, doctor_id]
          properties:
            patient_id:
              type: integer
            doctor_id:
              type: integer
              description: Médico responsable — debe ser un usuario activo de la clínica con rol médico o admin
            treatment_plan_id:
              type: integer
              description: Opcional — normalmente no existe todavía; se crea al aceptar
            name:
              type: string
              example: Presupuesto - Revisión general
            treatment_type:
              type: string
              default: general
              description: "general, endodontics, orthodontics, implant, periodontics, prosthetics, surgery, whitening, other"
            tooth_number:
              type: string
            use_payment_plan:
              type: boolean
              default: false
              description: Si es false, toda la escalera de cuotas se guarda NULL
            calc_mode:
              type: string
              enum: [per_cita, total]
              description: Requerido si use_payment_plan=true
            num_citas:
              type: integer
              description: Requerido si use_payment_plan=true
            cost_per_cita:
              type: number
              format: float
              description: Requerido si use_payment_plan=true y calc_mode=per_cita
            total_amount:
              type: number
              format: float
              description: Requerido salvo que use_payment_plan=true y calc_mode=per_cita (ahí se deriva)
            down_payment:
              type: number
              format: float
              default: 0
              description: Ignorado si use_payment_plan=false
            start_date:
              type: string
              format: date
              description: Ignorado si use_payment_plan=false
            end_date:
              type: string
              format: date
              description: Ignorado si use_payment_plan=false
            notes:
              type: string
            items:
              type: array
              items:
                type: object
                required: [description, unit_price]
                properties:
                  description:
                    type: string
                  quantity:
                    type: integer
                    default: 1
                  unit_price:
                    type: number
                    format: float
    responses:
      201:
        description: Presupuesto creado
        schema:
          type: object
          properties:
            budget:
              $ref: '#/definitions/Budget'
            message:
              type: string
      400:
        description: Campo requerido faltante, médico o plan inválido, fecha inválida o ítem inválido
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    data = request.get_json()
    required = ["patient_id", "name", "doctor_id"]
    for field in required:
        if data.get(field) is None:
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    doctor = resolve_scoped_doctor(data["doctor_id"])
    if doctor is None:
        return jsonify({"error": "El médico responsable no es válido"}), 400

    treatment_plan_id = None
    if data.get("treatment_plan_id"):
        plan = resolve_scoped_treatment_plan(data["treatment_plan_id"], data["patient_id"])
        if plan is None:
            return jsonify({"error": "El plan de tratamiento no existe o no corresponde al paciente"}), 400
        treatment_plan_id = plan.id

    use_payment_plan = bool(data.get("use_payment_plan", False))
    num_citas = cost_per_cita = down = None
    start_date_val = end_date_val = None

    if use_payment_plan:
        for field in ("num_citas", "calc_mode"):
            if data.get(field) is None:
                return jsonify({"error": f"Campo requerido: {field}"}), 400

        calc_mode = data["calc_mode"]
        if calc_mode not in ("per_cita", "total"):
            return jsonify({"error": "calc_mode debe ser 'per_cita' o 'total'"}), 400

        num_citas = int(data["num_citas"])
        if num_citas < 1:
            return jsonify({"error": "La cantidad de citas debe ser al menos 1"}), 400
        down = float(data.get("down_payment", 0))

        if calc_mode == "per_cita":
            if data.get("cost_per_cita") is None:
                return jsonify({"error": "Campo requerido: cost_per_cita"}), 400
            cost_per_cita = float(data["cost_per_cita"])
            total = round(down + num_citas * cost_per_cita, 2)
        else:
            if data.get("total_amount") is None:
                return jsonify({"error": "Campo requerido: total_amount"}), 400
            total = float(data["total_amount"])
            cost_per_cita = round((total - down) / num_citas, 2)

        if data.get("start_date"):
            try:
                start_date_val = date.fromisoformat(data["start_date"])
            except ValueError:
                return jsonify({"error": "Formato de fecha inválido"}), 400
        if data.get("end_date"):
            try:
                end_date_val = date.fromisoformat(data["end_date"])
            except ValueError:
                return jsonify({"error": "Formato de fecha inválido"}), 400
        if start_date_val and end_date_val and end_date_val < start_date_val:
            return jsonify({"error": "La fecha de fin no puede ser anterior a la fecha de inicio"}), 400
    else:
        # No ladder at all: every FINANCING_FIELDS stays None above, whatever the
        # client sent. total_amount is still NOT NULL — the form derives it from
        # the items subtotal.
        if data.get("total_amount") is None:
            return jsonify({"error": "Campo requerido: total_amount"}), 400
        total = float(data["total_amount"])

    items_data = data.get("items") or []
    for item_data in items_data:
        if not item_data.get("description") or item_data.get("unit_price") is None:
            return jsonify({"error": "Cada ítem requiere descripción y precio unitario"}), 400

    budget = Budget(
        clinic_id=current.clinic_id,
        patient_id=data["patient_id"],
        treatment_plan_id=treatment_plan_id,
        doctor_id=doctor.id,
        created_by_id=current.id,
        name=data["name"],
        treatment_type=data.get("treatment_type") or "general",
        tooth_number=data.get("tooth_number") or None,
        total_amount=total,
        use_payment_plan=use_payment_plan,
        down_payment=down,
        num_citas=num_citas,
        cost_per_cita=cost_per_cita,
        start_date=start_date_val,
        end_date=end_date_val,
        notes=data.get("notes"),
    )
    db.session.add(budget)
    db.session.flush()  # get budget.id

    for item_data in items_data:
        qty = item_data.get("quantity", 1)
        unit_price = float(item_data["unit_price"])
        db.session.add(BudgetItem(
            clinic_id=current.clinic_id,
            budget_id=budget.id,
            description=item_data["description"],
            quantity=qty,
            unit_price=unit_price,
            total=qty * unit_price,
        ))

    db.session.commit()
    return jsonify({"budget": budget.to_dict(), "message": "Presupuesto creado"}), 201


@billing_bp.route("/budgets/<int:budget_id>", methods=["PUT"])
@clinical_access_required
def update_budget(budget_id):
    """
    Actualizar presupuesto
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Solo se pueden editar presupuestos en estado `draft` — una vez Aceptado o Rechazado
      queda de solo lectura. Si se envían `items`, reemplaza la lista completa.
      Apagar `use_payment_plan` borra (NULLea) toda la escalera de cuotas; encenderlo
      exige `num_citas`/`calc_mode` igual que al crear.
    parameters:
      - in: path
        name: budget_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            doctor_id:
              type: integer
              description: Debe ser un usuario activo de la clínica con rol médico o admin
            treatment_type:
              type: string
            tooth_number:
              type: string
            treatment_plan_id:
              type: integer
              description: Debe ser un plan del mismo paciente; null lo desvincula
            use_payment_plan:
              type: boolean
            calc_mode:
              type: string
              enum: [per_cita, total]
            num_citas:
              type: integer
            cost_per_cita:
              type: number
              format: float
            total_amount:
              type: number
              format: float
            down_payment:
              type: number
              format: float
            start_date:
              type: string
              format: date
            end_date:
              type: string
              format: date
            notes:
              type: string
            items:
              type: array
              items:
                type: object
    responses:
      200:
        description: Presupuesto actualizado
        schema:
          type: object
          properties:
            budget:
              $ref: '#/definitions/Budget'
            message:
              type: string
      400:
        description: Presupuesto no editable (no está en borrador), médico o plan inválido, cuotas inválidas o fecha inválida
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Presupuesto no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    budget = Budget.query.get_or_404(budget_id, description="Presupuesto no encontrado")
    if budget.status != BudgetStatus.DRAFT:
        return jsonify({"error": "Solo se pueden editar presupuestos en borrador"}), 400

    data = request.get_json() or {}
    if "name" in data:
        budget.name = data["name"]
    if "doctor_id" in data:
        doctor = resolve_scoped_doctor(data["doctor_id"])
        if doctor is None:
            return jsonify({"error": "El médico responsable no es válido"}), 400
        budget.doctor_id = doctor.id
    if "treatment_type" in data:
        budget.treatment_type = data["treatment_type"] or "general"
    if "tooth_number" in data:
        budget.tooth_number = data["tooth_number"] or None
    if "treatment_plan_id" in data:
        # Used to be a raw assignment of a client-sent FK — an id from another
        # clinic (or another patient) went straight into the column, since
        # Postgres doesn't apply RLS to FK checks. Resolve it scoped instead.
        if data["treatment_plan_id"]:
            plan = resolve_scoped_treatment_plan(data["treatment_plan_id"], budget.patient_id)
            if plan is None:
                return jsonify({"error": "El plan de tratamiento no existe o no corresponde al paciente"}), 400
            budget.treatment_plan_id = plan.id
        else:
            budget.treatment_plan_id = None
    if "notes" in data:
        budget.notes = data["notes"]

    use_payment_plan = bool(data.get("use_payment_plan", budget.use_payment_plan))

    if not use_payment_plan:
        # Whatever the client sent, an unfinanced budget carries no ladder.
        budget.use_payment_plan = False
        for field in FINANCING_FIELDS:
            setattr(budget, field, None)
        if "total_amount" in data:
            budget.total_amount = float(data["total_amount"])
    else:
        if "start_date" in data:
            if data["start_date"]:
                try:
                    budget.start_date = date.fromisoformat(data["start_date"])
                except ValueError:
                    return jsonify({"error": "Formato de fecha inválido"}), 400
            else:
                budget.start_date = None
        if "end_date" in data:
            if data["end_date"]:
                try:
                    budget.end_date = date.fromisoformat(data["end_date"])
                except ValueError:
                    return jsonify({"error": "Formato de fecha inválido"}), 400
            else:
                budget.end_date = None
        if budget.start_date and budget.end_date and budget.end_date < budget.start_date:
            return jsonify({"error": "La fecha de fin no puede ser anterior a la fecha de inicio"}), 400

        # Turning financing ON for a budget that had none: there are no stored
        # citas/cost to fall back on (they're NULL), so the ladder must arrive
        # complete — same requirement as create_budget.
        turning_on = not budget.use_payment_plan
        if turning_on:
            for field in ("num_citas", "calc_mode"):
                if data.get(field) is None:
                    return jsonify({"error": f"Campo requerido: {field}"}), 400
        budget.use_payment_plan = True

        if turning_on or any(f in data for f in ("total_amount", "down_payment", "cost_per_cita",
                                                 "calc_mode", "num_citas")):
            # Fall back to the stored value only when the key is absent — an
            # explicit 0 must reach the "al menos 1" check below, not be masked.
            # The `is not None` guards cover a previously unfinanced budget,
            # whose stored ladder is all NULL.
            num_citas_raw = data.get("num_citas", budget.num_citas)
            num_citas = int(num_citas_raw) if num_citas_raw is not None else 0
            if num_citas < 1:
                return jsonify({"error": "La cantidad de citas debe ser al menos 1"}), 400
            down_raw = data.get("down_payment", budget.down_payment)
            down = float(down_raw) if down_raw is not None else 0.0
            calc_mode = data.get("calc_mode")
            if calc_mode == "per_cita" or (calc_mode is None and "cost_per_cita" in data and "total_amount" not in data):
                cost_raw = data.get("cost_per_cita", budget.cost_per_cita)
                cost_per_cita = float(cost_raw) if cost_raw is not None else 0.0
                total = round(down + num_citas * cost_per_cita, 2)
            else:
                total = float(data.get("total_amount", budget.total_amount))
                cost_per_cita = round((total - down) / num_citas, 2)
            budget.num_citas = num_citas
            budget.down_payment = down
            budget.total_amount = total
            budget.cost_per_cita = cost_per_cita

    if "items" in data:
        items_data = data["items"] or []
        for item_data in items_data:
            if not item_data.get("description") or item_data.get("unit_price") is None:
                return jsonify({"error": "Cada ítem requiere descripción y precio unitario"}), 400
        budget.items.clear()
        db.session.flush()
        for item_data in items_data:
            qty = item_data.get("quantity", 1)
            unit_price = float(item_data["unit_price"])
            budget.items.append(BudgetItem(
                clinic_id=budget.clinic_id,
                description=item_data["description"],
                quantity=qty,
                unit_price=unit_price,
                total=qty * unit_price,
            ))

    db.session.commit()
    return jsonify({"budget": budget.to_dict(), "message": "Presupuesto actualizado"}), 200


@billing_bp.route("/budgets/<int:budget_id>/accept", methods=["POST"])
@clinical_access_required
def accept_budget(budget_id):
    """
    Aceptar presupuesto (crea el plan de tratamiento)
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Aceptar es lo que convierte la propuesta en un registro clínico: en la misma
      transacción se crea automáticamente el `TreatmentPlan` con el médico, el tipo y
      la pieza del presupuesto, y el presupuesto queda vinculado a él
      (`treatment_plan_id`). Contra ese plan ya se pueden agendar citas.
      Si el presupuesto ya tenía un plan vinculado a mano, se reusa ese en vez de crear
      otro. `total_sessions` se copia de `num_citas` sólo si el presupuesto está
      financiado — uno suelto no tiene cantidad de citas por diseño.
    parameters:
      - in: path
        name: budget_id
        type: integer
        required: true
    responses:
      200:
        description: Presupuesto aceptado y plan de tratamiento creado
        schema:
          type: object
          properties:
            budget:
              $ref: '#/definitions/Budget'
            treatment_plan:
              $ref: '#/definitions/TreatmentPlan'
            message:
              type: string
      400:
        description: El presupuesto no está en borrador, no tiene médico responsable, o su plan vinculado es inválido
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Presupuesto no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    # Row lock, same pattern as add_payment/register_installment. Two fast clicks
    # on "Aceptar" would otherwise both read DRAFT and each create a TreatmentPlan;
    # the second request blocks here until the first commits, then finds the status
    # already ACCEPTED and falls out on the 400 below — one budget, one plan.
    budget = Budget.query.filter_by(id=budget_id).with_for_update().first()
    if budget is None:
        return jsonify({"error": "Presupuesto no encontrado"}), 404
    if budget.status != BudgetStatus.DRAFT:
        return jsonify({"error": "Solo se pueden aceptar presupuestos en borrador"}), 400
    if budget.doctor_id is None:
        # Only reachable for budgets written before FCLI-16 that were never linked
        # to a treatment plan (the migration backfills doctor_id from the plan when
        # there was one). The route requires a doctor rather than guessing.
        return jsonify({
            "error": "El presupuesto no tiene médico responsable. Editalo y asignale uno antes de aceptarlo."
        }), 400

    plan = None
    if budget.treatment_plan_id:
        # Pre-FCLI-16 rows could get any treatment_plan_id assigned through the
        # PUT, which validated nothing — re-check it here before hanging the
        # acceptance off it.
        plan = resolve_scoped_treatment_plan(budget.treatment_plan_id, budget.patient_id)
        if plan is None:
            return jsonify({
                "error": "El plan de tratamiento vinculado no existe o no corresponde al paciente"
            }), 400

    if plan is None:
        # ── Deliberate role escalation, do not "fix" ──
        # This route is clinical_access_required, which includes RECEPTIONIST, while
        # POST /treatments/plans is medical_staff_required. So a receptionist
        # accepting a budget creates a TreatmentPlan she could not create directly.
        # That is correct: she authors nothing clinical — the doctor, type and tooth
        # were all chosen by whoever wrote the budget; accepting only transcribes a
        # proposal that was already authorized. Restricting it would break the real
        # flow: the receptionist is the one at the counter when the patient says yes.
        #
        # The safety line is doctor_id = budget.doctor_id, NEVER current.id. Note
        # create_treatment_plan (treatments.py) uses data.get("doctor_id", current.id);
        # copying that fallback here would credit the clinical plan to whoever clicked
        # Aceptar. That's why the model is built inline instead of calling that route.
        plan = TreatmentPlan(
            clinic_id=budget.clinic_id,
            patient_id=budget.patient_id,
            doctor_id=budget.doctor_id,
            name=budget.name,
            treatment_type=budget.treatment_type,
            tooth_number=budget.tooth_number,
            # An unfinanced budget has no cita count by design — leave it unplanned.
            total_sessions=budget.num_citas if budget.use_payment_plan else None,
            # Provenance only. budget.notes are commercial terms agreed with the
            # patient; they don't belong in a clinical field.
            notes=f"Creado automáticamente al aceptar el presupuesto #{budget.id}.",
        )
        db.session.add(plan)
        db.session.flush()  # get plan.id
        budget.treatment_plan_id = plan.id

    budget.status = BudgetStatus.ACCEPTED
    db.session.commit()
    return jsonify({
        "budget": budget.to_dict(),
        "treatment_plan": plan.to_dict(),
        "message": "Presupuesto aceptado y plan de tratamiento creado",
    }), 200


@billing_bp.route("/budgets/<int:budget_id>/reject", methods=["POST"])
@clinical_access_required
def reject_budget(budget_id):
    """
    Rechazar presupuesto
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: budget_id
        type: integer
        required: true
    responses:
      200:
        description: Presupuesto rechazado
        schema:
          type: object
          properties:
            budget:
              $ref: '#/definitions/Budget'
            message:
              type: string
      400:
        description: El presupuesto no está en borrador
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Presupuesto no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    budget = Budget.query.get_or_404(budget_id, description="Presupuesto no encontrado")
    if budget.status != BudgetStatus.DRAFT:
        return jsonify({"error": "Solo se pueden rechazar presupuestos en borrador"}), 400
    budget.status = BudgetStatus.REJECTED
    db.session.commit()
    return jsonify({"budget": budget.to_dict(), "message": "Presupuesto rechazado"}), 200


@billing_bp.route("/budgets/<int:budget_id>/link-plan", methods=["POST"])
@clinical_access_required
def link_budget_plan(budget_id):
    """
    Vincular presupuesto aceptado a un plan de pago generado
    ---
    tags:
      - Facturación
    security:
      - BearerAuth: []
    description: >
      Se llama después de crear el PaymentPlan precargado con las condiciones del
      presupuesto. Copia `treatment_plan_id` desde el plan de pago recién creado
      (nunca se confía en un valor enviado por el cliente para ese campo).
    parameters:
      - in: path
        name: budget_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [payment_plan_id]
          properties:
            payment_plan_id:
              type: integer
    responses:
      200:
        description: Presupuesto vinculado al plan de pago
        schema:
          type: object
          properties:
            budget:
              $ref: '#/definitions/Budget'
            message:
              type: string
      400:
        description: El presupuesto no está aceptado, ya fue convertido, el plan no existe, pertenece a otro paciente o ya está vinculado a otro presupuesto
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Presupuesto no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    budget = Budget.query.get_or_404(budget_id, description="Presupuesto no encontrado")
    if budget.status != BudgetStatus.ACCEPTED:
        return jsonify({"error": "Solo se puede vincular un plan a un presupuesto aceptado"}), 400
    if budget.converted_plan_id is not None:
        return jsonify({"error": "Este presupuesto ya fue convertido a un plan de pago"}), 400
    # Symmetric to create_invoice's exclusivity guard: financing a budget and
    # charging it per item are two ways to collect the same money. Financing
    # "later" stays available exactly while nothing has been charged yet, and
    # closes the moment the first comprobante is issued.
    if budget.has_billing:
        return jsonify({
            "error": "Este presupuesto ya tiene comprobantes emitidos y se cobra por ítem; "
                     "no puede financiarse con un plan de pago"
        }), 400

    data = request.get_json() or {}
    plan_id = data.get("payment_plan_id")
    if not plan_id:
        return jsonify({"error": "Campo requerido: payment_plan_id"}), 400

    plan = PaymentPlan.query.get_or_404(plan_id, description="Plan de pago no encontrado")
    if plan.patient_id != budget.patient_id:
        return jsonify({"error": "El plan de pago no corresponde al mismo paciente del presupuesto"}), 400
    if Budget.query.filter(Budget.converted_plan_id == plan.id, Budget.id != budget.id).first():
        return jsonify({"error": "Este plan de pago ya está vinculado a otro presupuesto"}), 400

    budget.converted_plan_id = plan.id
    budget.treatment_plan_id = plan.treatment_plan_id
    db.session.commit()
    return jsonify({"budget": budget.to_dict(), "message": "Presupuesto vinculado al plan de pago"}), 200
