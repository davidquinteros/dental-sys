from flask import Blueprint, request, jsonify
from app import db
from app.models.billing import Invoice, InvoiceItem, Payment, PaymentPlan, InvoiceStatus, PaymentMethod
from app.middleware.auth import clinical_access_required, admin_required, get_current_user
from app.models.user import UserRole
from datetime import datetime, date

billing_bp = Blueprint("billing", __name__)


def generate_invoice_number() -> str:
    """Generate sequential invoice number like INV-2025-0001"""
    year = datetime.utcnow().year
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
    status = request.args.get("status")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Invoice.query
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
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
        description: patient_id faltante, sin ítems, ítem incompleto, o fecha inválida
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

    invoice = Invoice(
        clinic_id=current.clinic_id,
        invoice_number=generate_invoice_number(),
        patient_id=data["patient_id"],
        appointment_id=data.get("appointment_id"),
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

    for item_data in items_data:
        if not item_data.get("description") or not item_data.get("unit_price"):
            return jsonify({"error": "Cada ítem requiere descripción y precio unitario"}), 400

        qty = item_data.get("quantity", 1)
        unit_price = float(item_data["unit_price"])
        item = InvoiceItem(
            invoice_id=invoice.id,
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
    description: No se puede modificar una factura ya pagada o cancelada.
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
        description: La factura ya está pagada o cancelada
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
    if "discount" in data:
        invoice.discount = float(data["discount"])
    if "notes" in data:
        invoice.notes = data["notes"]
    if "status" in data and data["status"] == "cancelled":
        invoice.status = InvoiceStatus.CANCELLED

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
              enum: [cash, card, transfer, other]
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
    invoice = Invoice.query.get_or_404(invoice_id, description="Factura no encontrada")

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

    if amount < float(invoice.balance):
        return jsonify({"error": "Solo se aceptan pagos totales. Use un plan de pago para pagos en cuotas."}), 400

    try:
        method = PaymentMethod(data.get("method", "cash"))
    except ValueError:
        method = PaymentMethod.CASH

    payment = Payment(
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
      Asociado a un plan de tratamiento. Calcula automáticamente `installment_amount`
      = (total_amount - down_payment) / installments, e inicializa `total_paid` con el down_payment.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [patient_id, treatment_plan_id, name, total_amount, installments]
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
            total_amount:
              type: number
              format: float
              example: 4500.0
            down_payment:
              type: number
              format: float
              default: 0
              example: 900.0
            installments:
              type: integer
              example: 12
            start_date:
              type: string
              format: date
              example: "2026-04-15"
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
    required = ["patient_id", "treatment_plan_id", "name", "total_amount", "installments"]
    for field in required:
        if data.get(field) is None:
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    installments = int(data["installments"])
    total = float(data["total_amount"])
    down = float(data.get("down_payment", 0))
    installment_amount = round((total - down) / installments, 2)

    plan = PaymentPlan(
        clinic_id=current.clinic_id,
        patient_id=data["patient_id"],
        treatment_plan_id=data["treatment_plan_id"],
        created_by_id=current.id,
        name=data["name"],
        total_amount=total,
        down_payment=down,
        installments=installments,
        installment_amount=installment_amount,
        total_paid=down,
        notes=data.get("notes"),
    )

    if data.get("start_date"):
        try:
            plan.start_date = date.fromisoformat(data["start_date"])
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido"}), 400

    db.session.add(plan)
    db.session.commit()

    return jsonify({"payment_plan": plan.to_dict(), "message": "Plan de pago creado"}), 201


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
      Incrementa `paid_installments` y suma el monto a `total_paid`. Si se completan
      todas las cuotas, el plan pasa a estado `completed`.
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
            amount:
              type: number
              format: float
              description: Por defecto, el valor de `installment_amount` del plan
    responses:
      200:
        description: Cuota registrada
        schema:
          type: object
          properties:
            payment_plan:
              $ref: '#/definitions/PaymentPlan'
            message:
              type: string
      400:
        description: Todas las cuotas ya fueron pagadas
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
    plan = PaymentPlan.query.get_or_404(plan_id)
    data = request.get_json() or {}

    if plan.paid_installments >= plan.installments:
        return jsonify({"error": "Todas las cuotas ya fueron pagadas"}), 400

    amount = float(data.get("amount", plan.installment_amount))
    plan.paid_installments += 1
    plan.total_paid = float(plan.total_paid) + amount

    if plan.paid_installments >= plan.installments:
        from app.models.billing import PaymentPlanStatus
        plan.status = PaymentPlanStatus.COMPLETED

    db.session.commit()
    return jsonify({"payment_plan": plan.to_dict(), "message": "Cuota registrada"}), 200


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
    description: Totales generales de facturación (histórico completo, sin filtro de fechas).
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
    total_invoiced = db.session.query(func.sum(Invoice.total)).scalar() or 0
    total_collected = db.session.query(func.sum(Invoice.amount_paid)).scalar() or 0
    pending = db.session.query(func.sum(Invoice.balance)).filter(
        Invoice.status == InvoiceStatus.PENDING
    ).scalar() or 0

    return jsonify({
        "total_invoiced": float(total_invoiced),
        "total_collected": float(total_collected),
        "pending_balance": float(pending),
    }), 200
