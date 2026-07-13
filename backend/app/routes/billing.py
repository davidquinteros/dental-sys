from flask import Blueprint, request, jsonify
from app import db
from app.models.billing import (
    Invoice, InvoiceItem, Payment, PaymentPlan, PaymentPlanInstallment,
    InvoiceStatus, PaymentMethod, PaymentPlanStatus,
    Budget, BudgetItem, BudgetStatus,
)
from app.middleware.auth import clinical_access_required, admin_required, get_current_user
from app.models.user import UserRole
from app.utils.clinic_time import local_now
from datetime import datetime, date

billing_bp = Blueprint("billing", __name__)

# Only these are offered for new payments in this deliverable; other
# PaymentMethod members are legacy values kept for existing rows (see model).
ALLOWED_PAYMENT_METHODS = [PaymentMethod.CASH, PaymentMethod.QR]


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
            clinic_id=invoice.clinic_id,
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
            if not item_data.get("description") or not item_data.get("unit_price"):
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
      plan pasa a `completed` cuando `balance` llega a 0.
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
        description: El plan ya está completamente pagado, o el monto/cantidad de citas es inválido
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

    if "count" in data:
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

    query = Budget.query
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if status:
        query = query.filter_by(status=status)

    budgets = query.order_by(Budget.created_at.desc()).all()
    return jsonify({"budgets": [b.to_dict() for b in budgets], "total": len(budgets)}), 200


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
    budget = Budget.query.get_or_404(budget_id, description="Presupuesto no encontrado")
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
      El plan de tratamiento suele no existir todavía (treatment_plan_id es opcional) —
      normalmente se elige/crea recién al convertir un presupuesto Aceptado en un plan de
      pago. `items` es una lista opcional, puramente descriptiva de lo observado/propuesto;
      no condiciona `total_amount`, que se calcula igual que en un plan de pago según
      `calc_mode` (`per_cita`: se envía `cost_per_cita` y se deriva `total_amount`; `total`:
      se envía `total_amount` y se deriva `cost_per_cita`).
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [patient_id, name, num_citas, calc_mode]
          properties:
            patient_id:
              type: integer
            treatment_plan_id:
              type: integer
              description: Opcional — normalmente no existe todavía
            name:
              type: string
              example: Presupuesto - Revisión general
            calc_mode:
              type: string
              enum: [per_cita, total]
            num_citas:
              type: integer
            cost_per_cita:
              type: number
              format: float
              description: Requerido si calc_mode=per_cita
            total_amount:
              type: number
              format: float
              description: Requerido si calc_mode=total
            down_payment:
              type: number
              format: float
              default: 0
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
        description: Campo requerido faltante, fecha inválida o ítem inválido
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
    required = ["patient_id", "name", "num_citas", "calc_mode"]
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

    items_data = data.get("items") or []
    for item_data in items_data:
        if not item_data.get("description") or item_data.get("unit_price") is None:
            return jsonify({"error": "Cada ítem requiere descripción y precio unitario"}), 400

    budget = Budget(
        clinic_id=current.clinic_id,
        patient_id=data["patient_id"],
        treatment_plan_id=data.get("treatment_plan_id"),
        created_by_id=current.id,
        name=data["name"],
        total_amount=total,
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
            treatment_plan_id:
              type: integer
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
        description: Presupuesto no editable (no está en borrador), cuotas inválidas o fecha inválida
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
    if "treatment_plan_id" in data:
        budget.treatment_plan_id = data["treatment_plan_id"]
    if "notes" in data:
        budget.notes = data["notes"]
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

    if any(f in data for f in ("total_amount", "down_payment", "cost_per_cita", "calc_mode", "num_citas")):
        num_citas = int(data.get("num_citas", budget.num_citas))
        if num_citas < 1:
            return jsonify({"error": "La cantidad de citas debe ser al menos 1"}), 400
        down = float(data.get("down_payment", budget.down_payment))
        calc_mode = data.get("calc_mode")
        if calc_mode == "per_cita" or (calc_mode is None and "cost_per_cita" in data and "total_amount" not in data):
            cost_per_cita = float(data.get("cost_per_cita", budget.cost_per_cita))
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
    Aceptar presupuesto
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
        description: Presupuesto aceptado
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
        return jsonify({"error": "Solo se pueden aceptar presupuestos en borrador"}), 400
    budget.status = BudgetStatus.ACCEPTED
    db.session.commit()
    return jsonify({"budget": budget.to_dict(), "message": "Presupuesto aceptado"}), 200


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
