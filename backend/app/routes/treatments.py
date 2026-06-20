from flask import Blueprint, request, jsonify
from app import db
from app.models.treatment import Treatment, TreatmentPlan, TreatmentPlanStatus
from app.middleware.auth import medical_staff_required, clinical_access_required, get_current_user
from datetime import date

treatments_bp = Blueprint("treatments", __name__)


# ─── TREATMENTS (Single sessions) ────────────────────────────────────────────

@treatments_bp.route("/", methods=["GET"])
@clinical_access_required
def list_treatments():
    """
    Listar atenciones
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: patient_id
        type: integer
      - in: query
        name: doctor_id
        type: integer
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
        description: Lista paginada de atenciones (más recientes primero)
        schema:
          type: object
          properties:
            treatments:
              type: array
              items:
                $ref: '#/definitions/Treatment'
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
    patient_id = request.args.get("patient_id", type=int)
    doctor_id = request.args.get("doctor_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Treatment.query
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if doctor_id:
        query = query.filter_by(doctor_id=doctor_id)

    pagination = query.order_by(Treatment.performed_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "treatments": [t.to_dict() for t in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
    }), 200


@treatments_bp.route("/<int:treatment_id>", methods=["GET"])
@clinical_access_required
def get_treatment(treatment_id):
    """
    Obtener atención por ID
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: treatment_id
        type: integer
        required: true
    responses:
      200:
        description: Datos de la atención
        schema:
          type: object
          properties:
            treatment:
              $ref: '#/definitions/Treatment'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Tratamiento no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    treatment = Treatment.query.get_or_404(treatment_id, description="Tratamiento no encontrado")
    return jsonify({"treatment": treatment.to_dict()}), 200


@treatments_bp.route("/", methods=["POST"])
@medical_staff_required
def create_treatment():
    """
    Registrar atención clínica
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    description: >
      Solo personal médico (admin, médico, asistente). Si se vincula a un plan de tratamiento
      (`treatment_plan_id`), incrementa automáticamente el contador `completed_sessions` del plan.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [patient_id, procedure]
          properties:
            patient_id:
              type: integer
              example: 3
            doctor_id:
              type: integer
              description: Por defecto, el usuario autenticado
            appointment_id:
              type: integer
              description: Cita asociada (opcional)
            treatment_plan_id:
              type: integer
              description: Plan de tratamiento asociado (opcional)
            diagnosis:
              type: string
            procedure:
              type: string
              example: Extracción dental pieza 38
            tooth_number:
              type: string
              example: "38"
            tooth_surface:
              type: string
              example: O
            description:
              type: string
            clinical_notes:
              type: string
            prescriptions:
              type: string
            next_steps:
              type: string
    responses:
      201:
        description: Atención registrada correctamente
        schema:
          type: object
          properties:
            treatment:
              $ref: '#/definitions/Treatment'
            message:
              type: string
      400:
        description: Campo requerido faltante
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado (requiere personal médico)
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    data = request.get_json()
    required = ["patient_id", "procedure"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    treatment = Treatment(
        clinic_id=current.clinic_id,
        patient_id=data["patient_id"],
        doctor_id=data.get("doctor_id", current.id),
        appointment_id=data.get("appointment_id"),
        treatment_plan_id=data.get("treatment_plan_id"),
        diagnosis=data.get("diagnosis"),
        procedure=data["procedure"],
        tooth_number=data.get("tooth_number"),
        tooth_surface=data.get("tooth_surface"),
        description=data.get("description"),
        clinical_notes=data.get("clinical_notes"),
        prescriptions=data.get("prescriptions"),
        next_steps=data.get("next_steps"),
    )

    # Update plan session count if linked
    if treatment.treatment_plan_id:
        plan = TreatmentPlan.query.get(treatment.treatment_plan_id)
        if plan:
            plan.completed_sessions += 1

    db.session.add(treatment)
    db.session.commit()

    return jsonify({"treatment": treatment.to_dict(), "message": "Atención registrada correctamente"}), 201


@treatments_bp.route("/<int:treatment_id>", methods=["PUT"])
@medical_staff_required
def update_treatment(treatment_id):
    """
    Actualizar atención
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    description: Solo personal médico (admin, médico, asistente).
    parameters:
      - in: path
        name: treatment_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            diagnosis:
              type: string
            procedure:
              type: string
            tooth_number:
              type: string
            tooth_surface:
              type: string
            description:
              type: string
            clinical_notes:
              type: string
            prescriptions:
              type: string
            next_steps:
              type: string
    responses:
      200:
        description: Atención actualizada
        schema:
          type: object
          properties:
            treatment:
              $ref: '#/definitions/Treatment'
            message:
              type: string
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado (requiere personal médico)
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Tratamiento no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    treatment = Treatment.query.get_or_404(treatment_id)
    data = request.get_json()

    fields = [
        "diagnosis", "procedure", "tooth_number", "tooth_surface",
        "description", "clinical_notes", "prescriptions", "next_steps",
    ]
    for field in fields:
        if field in data:
            setattr(treatment, field, data[field])

    db.session.commit()
    return jsonify({"treatment": treatment.to_dict(), "message": "Atención actualizada"}), 200


# ─── TREATMENT PLANS ─────────────────────────────────────────────────────────

@treatments_bp.route("/plans", methods=["GET"])
@clinical_access_required
def list_treatment_plans():
    """
    Listar planes de tratamiento
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: patient_id
        type: integer
      - in: query
        name: status
        type: string
        enum: [active, completed, cancelled, on_hold]
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
        description: Lista paginada de planes de tratamiento (más recientes primero)
        schema:
          type: object
          properties:
            treatment_plans:
              type: array
              items:
                $ref: '#/definitions/TreatmentPlan'
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
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = TreatmentPlan.query
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(TreatmentPlan.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "treatment_plans": [tp.to_dict() for tp in pagination.items],
        "total": pagination.total,
    }), 200


@treatments_bp.route("/plans/<int:plan_id>", methods=["GET"])
@clinical_access_required
def get_treatment_plan(plan_id):
    """
    Obtener plan de tratamiento por ID
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: plan_id
        type: integer
        required: true
      - in: query
        name: include_sessions
        type: boolean
        default: false
        description: Si es true, incluye el detalle de cada sesión/atención del plan
    responses:
      200:
        description: Datos del plan de tratamiento
        schema:
          type: object
          properties:
            treatment_plan:
              $ref: '#/definitions/TreatmentPlan'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Plan no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    plan = TreatmentPlan.query.get_or_404(plan_id, description="Plan no encontrado")
    include_sessions = request.args.get("include_sessions", "false").lower() == "true"
    return jsonify({"treatment_plan": plan.to_dict(include_sessions=include_sessions)}), 200


@treatments_bp.route("/plans", methods=["POST"])
@medical_staff_required
def create_treatment_plan():
    """
    Crear plan de tratamiento
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    description: Solo personal médico (admin, médico, asistente). Útil para tratamientos multi-sesión (endodoncia, ortodoncia, implantes, etc.).
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [patient_id, name, treatment_type]
          properties:
            patient_id:
              type: integer
              example: 3
            doctor_id:
              type: integer
              description: Por defecto, el usuario autenticado
            name:
              type: string
              example: Ortodoncia completa - Brackets metálicos
            description:
              type: string
            treatment_type:
              type: string
              example: orthodontics
              description: "endodontics, orthodontics, implant, periodontics, prosthetics, surgery, whitening, other"
            total_sessions:
              type: integer
              example: 12
            tooth_number:
              type: string
            notes:
              type: string
            start_date:
              type: string
              format: date
              example: "2026-06-01"
            estimated_end_date:
              type: string
              format: date
              example: "2027-06-01"
    responses:
      201:
        description: Plan de tratamiento creado
        schema:
          type: object
          properties:
            treatment_plan:
              $ref: '#/definitions/TreatmentPlan'
            message:
              type: string
      400:
        description: Campo requerido faltante o formato de fecha inválido
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado (requiere personal médico)
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    data = request.get_json()
    required = ["patient_id", "name", "treatment_type"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    plan = TreatmentPlan(
        clinic_id=current.clinic_id,
        patient_id=data["patient_id"],
        doctor_id=data.get("doctor_id", current.id),
        name=data["name"],
        description=data.get("description"),
        treatment_type=data["treatment_type"],
        total_sessions=data.get("total_sessions"),
        tooth_number=data.get("tooth_number"),
        notes=data.get("notes"),
    )

    if data.get("start_date"):
        try:
            plan.start_date = date.fromisoformat(data["start_date"])
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido"}), 400

    if data.get("estimated_end_date"):
        try:
            plan.estimated_end_date = date.fromisoformat(data["estimated_end_date"])
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido"}), 400

    db.session.add(plan)
    db.session.commit()

    return jsonify({"treatment_plan": plan.to_dict(), "message": "Plan de tratamiento creado"}), 201


@treatments_bp.route("/plans/<int:plan_id>", methods=["PUT"])
@medical_staff_required
def update_treatment_plan(plan_id):
    """
    Actualizar plan de tratamiento
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    description: Solo personal médico (admin, médico, asistente).
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
            description:
              type: string
            total_sessions:
              type: integer
            notes:
              type: string
            tooth_number:
              type: string
            status:
              type: string
              enum: [active, completed, cancelled, on_hold]
            start_date:
              type: string
              format: date
            estimated_end_date:
              type: string
              format: date
            actual_end_date:
              type: string
              format: date
    responses:
      200:
        description: Plan actualizado
        schema:
          type: object
          properties:
            treatment_plan:
              $ref: '#/definitions/TreatmentPlan'
            message:
              type: string
      400:
        description: Estado o formato de fecha inválido
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado (requiere personal médico)
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Plan no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    plan = TreatmentPlan.query.get_or_404(plan_id)
    data = request.get_json()

    fields = ["name", "description", "total_sessions", "notes", "tooth_number"]
    for field in fields:
        if field in data:
            setattr(plan, field, data[field])

    if "status" in data:
        try:
            plan.status = TreatmentPlanStatus(data["status"])
        except ValueError:
            return jsonify({"error": "Estado inválido"}), 400

    for date_field in ["start_date", "estimated_end_date", "actual_end_date"]:
        if date_field in data and data[date_field]:
            try:
                setattr(plan, date_field, date.fromisoformat(data[date_field]))
            except ValueError:
                return jsonify({"error": f"Formato de fecha inválido en {date_field}"}), 400

    db.session.commit()
    return jsonify({"treatment_plan": plan.to_dict(), "message": "Plan actualizado"}), 200
