import secrets
import string
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from app import db
from app.models.clinic import Clinic
from app.models.user import User, UserRole
from app.models.subscription import SubscriptionTier, SubscriptionPayment, SubscriptionStatus
from app.middleware.auth import platform_admin_required, get_current_user
from app.utils.seeder import create_clinic

platform_bp = Blueprint("platform_admin", __name__)

VALID_STATUSES = [s.value for s in SubscriptionStatus]


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length - 1)) + secrets.choice("!@#$%*")
        if any(c.isupper() for c in pwd) and any(c.islower() for c in pwd) and any(c.isdigit() for c in pwd):
            return pwd


@platform_bp.route("/dashboard", methods=["GET"])
@platform_admin_required
def dashboard():
    """
    Resumen general de la plataforma
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    description: Conteos por estado de suscripción, usuarios totales, ingresos registrados y clínicas vencidas.
    responses:
      200:
        description: Estadísticas de la plataforma
        schema:
          type: object
          properties:
            total_clinics:
              type: integer
            clinics_by_status:
              type: object
            total_users:
              type: integer
            total_revenue:
              type: number
              format: float
            revenue_this_month:
              type: number
              format: float
            overdue_clinics:
              type: array
              items:
                $ref: '#/definitions/Clinic'
    """
    clinics = Clinic.query.all()
    clinics_by_status = {s.value: 0 for s in SubscriptionStatus}
    for c in clinics:
        clinics_by_status[c.subscription_status.value] += 1

    now = datetime.utcnow()
    month_start = date.today().replace(day=1)
    payments = SubscriptionPayment.query.all()
    total_revenue = sum(float(p.amount) for p in payments)
    revenue_this_month = sum(float(p.amount) for p in payments if p.payment_date >= month_start)

    overdue = [
        c for c in clinics
        if c.next_payment_due_at and c.next_payment_due_at < now
        and c.subscription_status not in (SubscriptionStatus.CANCELLED,)
    ]

    return jsonify({
        "total_clinics": len(clinics),
        "clinics_by_status": clinics_by_status,
        "total_users": User.query.count(),
        "total_revenue": total_revenue,
        "revenue_this_month": revenue_this_month,
        "overdue_clinics": [c.to_dict() for c in overdue],
    }), 200


@platform_bp.route("/clinics", methods=["GET"])
@platform_admin_required
def list_clinics():
    """
    Listar clínicas
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: status
        type: string
        required: false
        enum: [trial, active, past_due, suspended, cancelled]
        description: Filtra por estado de suscripción
    responses:
      200:
        description: Lista de clínicas con su estado de suscripción y cantidad de usuarios
        schema:
          type: object
          properties:
            clinics:
              type: array
              items:
                $ref: '#/definitions/Clinic'
    """
    query = Clinic.query
    status_filter = request.args.get("status")
    if status_filter:
        if status_filter not in VALID_STATUSES:
            return jsonify({"error": f"Estado inválido. Válidos: {VALID_STATUSES}"}), 400
        query = query.filter_by(subscription_status=SubscriptionStatus(status_filter))

    clinics = query.order_by(Clinic.created_at.desc()).all()
    result = []
    for c in clinics:
        data = c.to_dict()
        data["user_count"] = User.query.filter_by(clinic_id=c.id).count()
        result.append(data)

    return jsonify({"clinics": result, "total": len(result)}), 200


@platform_bp.route("/clinics", methods=["POST"])
@platform_admin_required
def create_clinic_route():
    """
    Crear clínica
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    description: Crea una clínica nueva (tenant) con su primer usuario administrador. Queda en periodo de prueba (trial) de 14 días.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [name, admin_email, admin_password]
          properties:
            name:
              type: string
              example: Clínica Sonrisas
            admin_email:
              type: string
              example: admin@sonrisas.com
            admin_password:
              type: string
              example: Sonrisas2025!
            admin_first_name:
              type: string
              example: Admin
            admin_last_name:
              type: string
              example: Sonrisas
            subscription_tier_id:
              type: integer
              required: false
    responses:
      201:
        description: Clínica creada correctamente
        schema:
          type: object
          properties:
            clinic:
              $ref: '#/definitions/Clinic'
            message:
              type: string
      400:
        description: Campo requerido faltante
        schema:
          $ref: '#/definitions/Error'
      409:
        description: El email del administrador ya está registrado
        schema:
          $ref: '#/definitions/Error'
    """
    data = request.get_json() or {}
    required = ["name", "admin_email", "admin_password"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    tier_id = data.get("subscription_tier_id")
    if tier_id is not None and not SubscriptionTier.query.get(tier_id):
        return jsonify({"error": "Tier de suscripción no encontrado"}), 400

    try:
        clinic = create_clinic(
            name=data["name"].strip(),
            admin_email=data["admin_email"],
            admin_password=data["admin_password"],
            admin_first_name=data.get("admin_first_name", "Admin"),
            admin_last_name=data.get("admin_last_name", ""),
            subscription_tier_id=tier_id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 409

    return jsonify({"clinic": clinic.to_dict(), "message": "Clínica creada correctamente"}), 201


@platform_bp.route("/clinics/<int:clinic_id>", methods=["GET"])
@platform_admin_required
def get_clinic(clinic_id):
    """
    Obtener detalle de una clínica
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: clinic_id
        type: integer
        required: true
    responses:
      200:
        description: Detalle de la clínica, sus administradores e historial de pagos
        schema:
          type: object
          properties:
            clinic:
              $ref: '#/definitions/Clinic'
            admins:
              type: array
              items:
                $ref: '#/definitions/User'
            payments:
              type: array
              items:
                $ref: '#/definitions/SubscriptionPayment'
            user_count:
              type: integer
      404:
        description: Clínica no encontrada
        schema:
          $ref: '#/definitions/Error'
    """
    clinic = Clinic.query.get_or_404(clinic_id, description="Clínica no encontrada")
    admins = User.query.filter_by(clinic_id=clinic_id, role=UserRole.ADMIN).all()
    payments = (SubscriptionPayment.query.filter_by(clinic_id=clinic_id)
                .order_by(SubscriptionPayment.payment_date.desc()).all())
    user_count = User.query.filter_by(clinic_id=clinic_id).count()

    return jsonify({
        "clinic": clinic.to_dict(),
        "admins": [a.to_dict() for a in admins],
        "payments": [p.to_dict() for p in payments],
        "user_count": user_count,
    }), 200


@platform_bp.route("/clinics/<int:clinic_id>", methods=["PUT"])
@platform_admin_required
def update_clinic(clinic_id):
    """
    Actualizar clínica
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: clinic_id
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
            is_active:
              type: boolean
            subscription_tier_id:
              type: integer
              nullable: true
            subscription_status:
              type: string
              enum: [trial, active, past_due, suspended, cancelled]
            notes:
              type: string
    responses:
      200:
        description: Clínica actualizada
        schema:
          type: object
          properties:
            clinic:
              $ref: '#/definitions/Clinic'
            message:
              type: string
      400:
        description: Valor inválido
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Clínica no encontrada
        schema:
          $ref: '#/definitions/Error'
    """
    clinic = Clinic.query.get_or_404(clinic_id, description="Clínica no encontrada")
    data = request.get_json() or {}

    if "name" in data:
        clinic.name = data["name"].strip()
    if "is_active" in data:
        clinic.is_active = bool(data["is_active"])
    if "notes" in data:
        clinic.notes = data["notes"]
    if "subscription_tier_id" in data:
        tier_id = data["subscription_tier_id"]
        if tier_id is not None and not SubscriptionTier.query.get(tier_id):
            return jsonify({"error": "Tier de suscripción no encontrado"}), 400
        clinic.subscription_tier_id = tier_id
    if "subscription_status" in data:
        if data["subscription_status"] not in VALID_STATUSES:
            return jsonify({"error": f"Estado inválido. Válidos: {VALID_STATUSES}"}), 400
        new_status = SubscriptionStatus(data["subscription_status"])
        clinic.subscription_status = new_status
        clinic.suspended_at = datetime.utcnow() if new_status == SubscriptionStatus.SUSPENDED else None

    db.session.commit()
    return jsonify({"clinic": clinic.to_dict(), "message": "Clínica actualizada"}), 200


@platform_bp.route("/clinics/<int:clinic_id>/reset-admin-password", methods=["POST"])
@platform_admin_required
def reset_admin_password(clinic_id):
    """
    Restaurar contraseña del administrador de una clínica
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    description: >
      Genera una contraseña temporal para el usuario administrador de la clínica y la
      devuelve una sola vez en la respuesta (no hay envío de correo). Si la clínica tiene
      más de un administrador, se debe indicar `user_id`.
    parameters:
      - in: path
        name: clinic_id
        type: integer
        required: true
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            user_id:
              type: integer
              description: Requerido si la clínica tiene más de un administrador
    responses:
      200:
        description: Contraseña temporal generada
        schema:
          type: object
          properties:
            user:
              $ref: '#/definitions/User'
            temporary_password:
              type: string
            message:
              type: string
      400:
        description: Hay varios administradores y no se indicó user_id
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Clínica o usuario administrador no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    Clinic.query.get_or_404(clinic_id, description="Clínica no encontrada")
    admins = User.query.filter_by(clinic_id=clinic_id, role=UserRole.ADMIN, is_active=True).all()
    if not admins:
        return jsonify({"error": "La clínica no tiene un administrador activo"}), 404

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")

    if user_id is not None:
        target = next((a for a in admins if a.id == user_id), None)
        if not target:
            return jsonify({"error": "Ese usuario no es administrador activo de esta clínica"}), 404
    elif len(admins) == 1:
        target = admins[0]
    else:
        return jsonify({
            "error": "La clínica tiene varios administradores, indique user_id",
            "admins": [{"id": a.id, "email": a.email, "full_name": a.full_name} for a in admins],
        }), 400

    temp_password = _generate_temp_password()
    target.set_password(temp_password)
    db.session.commit()

    return jsonify({
        "user": target.to_dict(),
        "temporary_password": temp_password,
        "message": "Contraseña restaurada. Compártala con el administrador de la clínica; no se mostrará de nuevo.",
    }), 200


@platform_bp.route("/subscription-tiers", methods=["GET"])
@platform_admin_required
def list_tiers():
    """
    Listar planes de suscripción
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    responses:
      200:
        description: Lista de planes
        schema:
          type: object
          properties:
            tiers:
              type: array
              items:
                $ref: '#/definitions/SubscriptionTier'
    """
    tiers = SubscriptionTier.query.order_by(SubscriptionTier.monthly_price).all()
    return jsonify({"tiers": [t.to_dict() for t in tiers]}), 200


@platform_bp.route("/subscription-tiers", methods=["POST"])
@platform_admin_required
def create_tier():
    """
    Crear plan de suscripción
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [name, code, monthly_price]
          properties:
            name:
              type: string
              example: Profesional
            code:
              type: string
              example: profesional
            monthly_price:
              type: number
              format: float
              example: 59.0
            max_users:
              type: integer
              nullable: true
            description:
              type: string
    responses:
      201:
        description: Plan creado
        schema:
          type: object
          properties:
            tier:
              $ref: '#/definitions/SubscriptionTier'
            message:
              type: string
      400:
        description: Campo requerido faltante
        schema:
          $ref: '#/definitions/Error'
      409:
        description: El código ya existe
        schema:
          $ref: '#/definitions/Error'
    """
    data = request.get_json() or {}
    required = ["name", "code", "monthly_price"]
    for field in required:
        if data.get(field) is None:
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    code = data["code"].strip().lower()
    if SubscriptionTier.query.filter_by(code=code).first():
        return jsonify({"error": "Ese código de plan ya existe"}), 409

    tier = SubscriptionTier(
        name=data["name"].strip(),
        code=code,
        monthly_price=data["monthly_price"],
        max_users=data.get("max_users"),
        description=data.get("description"),
    )
    db.session.add(tier)
    db.session.commit()
    return jsonify({"tier": tier.to_dict(), "message": "Plan creado correctamente"}), 201


@platform_bp.route("/subscription-tiers/<int:tier_id>", methods=["PUT"])
@platform_admin_required
def update_tier(tier_id):
    """
    Actualizar plan de suscripción
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: tier_id
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
            monthly_price:
              type: number
              format: float
            max_users:
              type: integer
              nullable: true
            description:
              type: string
            is_active:
              type: boolean
    responses:
      200:
        description: Plan actualizado
        schema:
          type: object
          properties:
            tier:
              $ref: '#/definitions/SubscriptionTier'
            message:
              type: string
      404:
        description: Plan no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    tier = SubscriptionTier.query.get_or_404(tier_id, description="Plan no encontrado")
    data = request.get_json() or {}
    for field in ["name", "monthly_price", "max_users", "description"]:
        if field in data:
            setattr(tier, field, data[field])
    if "is_active" in data:
        tier.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify({"tier": tier.to_dict(), "message": "Plan actualizado"}), 200


@platform_bp.route("/clinics/<int:clinic_id>/payments", methods=["GET"])
@platform_admin_required
def list_payments(clinic_id):
    """
    Listar pagos de suscripción de una clínica
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: clinic_id
        type: integer
        required: true
    responses:
      200:
        description: Historial de pagos
        schema:
          type: object
          properties:
            payments:
              type: array
              items:
                $ref: '#/definitions/SubscriptionPayment'
      404:
        description: Clínica no encontrada
        schema:
          $ref: '#/definitions/Error'
    """
    Clinic.query.get_or_404(clinic_id, description="Clínica no encontrada")
    payments = (SubscriptionPayment.query.filter_by(clinic_id=clinic_id)
                .order_by(SubscriptionPayment.payment_date.desc()).all())
    return jsonify({"payments": [p.to_dict() for p in payments]}), 200


@platform_bp.route("/clinics/<int:clinic_id>/payments", methods=["POST"])
@platform_admin_required
def record_payment(clinic_id):
    """
    Registrar pago de suscripción
    ---
    tags:
      - Plataforma
    security:
      - BearerAuth: []
    description: >
      Registro manual de un pago (no hay pasarela integrada). Al registrar un pago,
      la clínica pasa a estado `active` si estaba `past_due` o `suspended`, y se
      actualiza `next_payment_due_at` con `period_end` (o, si no se indica, 30 días
      desde hoy).
    parameters:
      - in: path
        name: clinic_id
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
              example: 59.0
            payment_date:
              type: string
              format: date
              description: Por defecto, hoy
            period_start:
              type: string
              format: date
            period_end:
              type: string
              format: date
            notes:
              type: string
    responses:
      201:
        description: Pago registrado
        schema:
          type: object
          properties:
            payment:
              $ref: '#/definitions/SubscriptionPayment'
            clinic:
              $ref: '#/definitions/Clinic'
            message:
              type: string
      400:
        description: Campo requerido faltante o fecha inválida
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Clínica no encontrada
        schema:
          $ref: '#/definitions/Error'
    """
    clinic = Clinic.query.get_or_404(clinic_id, description="Clínica no encontrada")
    data = request.get_json() or {}
    if data.get("amount") is None:
        return jsonify({"error": "Campo requerido: amount"}), 400

    try:
        payment_date = date.fromisoformat(data["payment_date"]) if data.get("payment_date") else date.today()
        period_start = date.fromisoformat(data["period_start"]) if data.get("period_start") else None
        period_end = date.fromisoformat(data["period_end"]) if data.get("period_end") else None
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido, use YYYY-MM-DD"}), 400

    current = get_current_user()
    payment = SubscriptionPayment(
        clinic_id=clinic_id,
        amount=data["amount"],
        payment_date=payment_date,
        period_start=period_start,
        period_end=period_end,
        notes=data.get("notes"),
        recorded_by_id=current.id,
    )
    db.session.add(payment)

    clinic.next_payment_due_at = (
        datetime.combine(period_end, datetime.min.time()) if period_end
        else datetime.utcnow() + timedelta(days=30)
    )
    if clinic.subscription_status in (SubscriptionStatus.PAST_DUE, SubscriptionStatus.SUSPENDED, SubscriptionStatus.TRIAL):
        clinic.subscription_status = SubscriptionStatus.ACTIVE
        clinic.suspended_at = None

    db.session.commit()
    return jsonify({
        "payment": payment.to_dict(), "clinic": clinic.to_dict(), "message": "Pago registrado correctamente",
    }), 201
