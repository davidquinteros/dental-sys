from flask import Blueprint, request, jsonify
from app import db
from app.models.patient import Patient
from app.middleware.auth import clinical_access_required, get_current_user
from datetime import date

patients_bp = Blueprint("patients", __name__)


@patients_bp.route("/", methods=["GET"])
@clinical_access_required
def list_patients():
    """
    Listar pacientes
    ---
    tags:
      - Pacientes
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
      - in: query
        name: per_page
        type: integer
        default: 20
      - in: query
        name: search
        type: string
        description: Busca por nombre, apellido, documento, teléfono o email
    responses:
      200:
        description: Lista paginada de pacientes activos
        schema:
          type: object
          properties:
            patients:
              type: array
              items:
                $ref: '#/definitions/Patient'
            total:
              type: integer
            pages:
              type: integer
            current_page:
              type: integer
            per_page:
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
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "").strip()

    query = Patient.query.filter_by(is_active=True)

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.document_number.ilike(like),
                Patient.phone.ilike(like),
                Patient.email.ilike(like),
            )
        )

    pagination = query.order_by(Patient.first_name).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "patients": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
        "per_page": per_page,
    }), 200


@patients_bp.route("/<int:patient_id>", methods=["GET"])
@clinical_access_required
def get_patient(patient_id):
    """
    Obtener paciente por ID
    ---
    tags:
      - Pacientes
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: patient_id
        type: integer
        required: true
      - in: query
        name: include_history
        type: boolean
        default: false
        description: Si es true, incluye conteos de citas/tratamientos/planes activos
    responses:
      200:
        description: Datos del paciente
        schema:
          type: object
          properties:
            patient:
              $ref: '#/definitions/Patient'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Paciente no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    patient = Patient.query.get_or_404(patient_id, description="Paciente no encontrado")
    include_history = request.args.get("include_history", "false").lower() == "true"
    return jsonify({"patient": patient.to_dict(include_history=include_history)}), 200


@patients_bp.route("/", methods=["POST"])
@clinical_access_required
def create_patient():
    """
    Registrar paciente
    ---
    tags:
      - Pacientes
    security:
      - BearerAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [first_name, last_name, document_number]
          properties:
            first_name:
              type: string
              example: Juan
            last_name:
              type: string
              example: Pérez
            document_number:
              type: string
              example: "1234567"
            document_type:
              type: string
              default: CI
              example: CI
            date_of_birth:
              type: string
              format: date
              example: "1990-05-15"
            gender:
              type: string
              example: M
            phone:
              type: string
              example: "591-70011111"
            phone_emergency:
              type: string
            email:
              type: string
              example: juan.perez@example.com
            address:
              type: string
            city:
              type: string
              example: La Paz
            blood_type:
              type: string
              enum: [A+, A-, B+, B-, AB+, AB-, O+, O-, unknown]
              default: unknown
            allergies:
              type: string
              example: Penicilina
            medical_notes:
              type: string
    responses:
      201:
        description: Paciente registrado correctamente
        schema:
          type: object
          properties:
            patient:
              $ref: '#/definitions/Patient'
            message:
              type: string
      400:
        description: Campo requerido faltante o formato de fecha incorrecto
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
      409:
        description: Ya existe un paciente con ese número de documento
        schema:
          $ref: '#/definitions/Error'
    """
    data = request.get_json()
    required = ["first_name", "last_name", "document_number"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    if Patient.query.filter_by(document_number=data["document_number"]).first():
        return jsonify({"error": "Ya existe un paciente con ese número de documento"}), 409

    try:
        dob = None
        if data.get("date_of_birth"):
            dob = date.fromisoformat(data["date_of_birth"])
    except ValueError:
        return jsonify({"error": "Formato de fecha incorrecto. Use YYYY-MM-DD"}), 400

    patient = Patient(
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        document_number=data["document_number"].strip(),
        document_type=data.get("document_type", "CI"),
        date_of_birth=dob,
        gender=data.get("gender"),
        phone=data.get("phone"),
        phone_emergency=data.get("phone_emergency"),
        email=data.get("email"),
        address=data.get("address"),
        city=data.get("city"),
        blood_type=data.get("blood_type", "unknown"),
        allergies=data.get("allergies"),
        medical_notes=data.get("medical_notes"),
    )

    db.session.add(patient)
    db.session.commit()

    return jsonify({"patient": patient.to_dict(), "message": "Paciente registrado correctamente"}), 201


@patients_bp.route("/<int:patient_id>", methods=["PUT"])
@clinical_access_required
def update_patient(patient_id):
    """
    Actualizar paciente
    ---
    tags:
      - Pacientes
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: patient_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            first_name:
              type: string
            last_name:
              type: string
            phone:
              type: string
            phone_emergency:
              type: string
            email:
              type: string
            address:
              type: string
            city:
              type: string
            allergies:
              type: string
            medical_notes:
              type: string
            blood_type:
              type: string
              enum: [A+, A-, B+, B-, AB+, AB-, O+, O-, unknown]
            gender:
              type: string
            document_type:
              type: string
            date_of_birth:
              type: string
              format: date
    responses:
      200:
        description: Paciente actualizado
        schema:
          type: object
          properties:
            patient:
              $ref: '#/definitions/Patient'
            message:
              type: string
      400:
        description: Formato de fecha incorrecto
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
        description: Paciente no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    patient = Patient.query.get_or_404(patient_id, description="Paciente no encontrado")
    data = request.get_json()

    updatable = [
        "first_name", "last_name", "phone", "phone_emergency",
        "email", "address", "city", "allergies", "medical_notes",
        "blood_type", "gender", "document_type",
    ]
    for field in updatable:
        if field in data:
            setattr(patient, field, data[field])

    if "date_of_birth" in data and data["date_of_birth"]:
        try:
            patient.date_of_birth = date.fromisoformat(data["date_of_birth"])
        except ValueError:
            return jsonify({"error": "Formato de fecha incorrecto"}), 400

    db.session.commit()
    return jsonify({"patient": patient.to_dict(), "message": "Paciente actualizado"}), 200


@patients_bp.route("/<int:patient_id>", methods=["DELETE"])
@clinical_access_required
def delete_patient(patient_id):
    """
    Desactivar paciente
    ---
    tags:
      - Pacientes
    security:
      - BearerAuth: []
    description: Baja lógica (soft delete).
    parameters:
      - in: path
        name: patient_id
        type: integer
        required: true
    responses:
      200:
        description: Paciente desactivado
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Paciente no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    patient = Patient.query.get_or_404(patient_id)
    patient.is_active = False
    db.session.commit()
    return jsonify({"message": "Paciente desactivado"}), 200


@patients_bp.route("/<int:patient_id>/odontogram", methods=["GET"])
@clinical_access_required
def get_odontogram(patient_id):
    """Obtener odontograma del paciente"""
    patient = Patient.query.get_or_404(patient_id, description="Paciente no encontrado")
    return jsonify(patient.odontogram or {}), 200


@patients_bp.route("/<int:patient_id>/odontogram", methods=["PUT"])
@clinical_access_required
def save_odontogram(patient_id):
    """Guardar odontograma del paciente"""
    patient = Patient.query.get_or_404(patient_id, description="Paciente no encontrado")
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Formato inválido"}), 400
    patient.odontogram = data
    db.session.commit()
    return jsonify(patient.odontogram), 200


@patients_bp.route("/<int:patient_id>/history", methods=["GET"])
@clinical_access_required
def patient_history(patient_id):
    """
    Historial completo del paciente
    ---
    tags:
      - Pacientes
    security:
      - BearerAuth: []
    description: Devuelve el paciente junto con todas sus citas, atenciones y planes de tratamiento (más recientes primero).
    parameters:
      - in: path
        name: patient_id
        type: integer
        required: true
    responses:
      200:
        description: Historial del paciente
        schema:
          type: object
          properties:
            patient:
              $ref: '#/definitions/Patient'
            appointments:
              type: array
              items:
                $ref: '#/definitions/Appointment'
            treatments:
              type: array
              items:
                $ref: '#/definitions/Treatment'
            treatment_plans:
              type: array
              items:
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
        description: Paciente no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    patient = Patient.query.get_or_404(patient_id, description="Paciente no encontrado")

    appointments = patient.appointments.order_by(
        db.desc("scheduled_at")
    ).all()

    treatments = patient.treatments.order_by(
        db.desc("performed_at")
    ).all()

    treatment_plans = patient.treatment_plans.order_by(
        db.desc("created_at")
    ).all()

    return jsonify({
        "patient": patient.to_dict(),
        "appointments": [a.to_dict() for a in appointments],
        "treatments": [t.to_dict() for t in treatments],
        "treatment_plans": [tp.to_dict() for tp in treatment_plans],
    }), 200
