from flask import Blueprint, request, jsonify, Response
from app import db
from app.models.treatment import Treatment, TreatmentPlan, TreatmentPlanStatus
from app.models.treatment_image import TreatmentImage
from app.middleware.auth import medical_staff_required, clinical_access_required, doctor_or_admin_required, get_current_user
from app.utils import storage
from datetime import date
from sqlalchemy.orm import joinedload
import uuid

treatments_bp = Blueprint("treatments", __name__)

# ─── Clinical images (photos per appointment / treatment plan) ───────────────
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
# Hard server-side ceiling. The frontend compresses before upload (canvas →
# JPEG), so real payloads are ~150-400KB; this is just a backstop against an
# uncompressed or malicious upload, not the expected size.
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB
_EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _validate_medications(medications) -> str | None:
    """Returns an error message if any medication is missing name/dosage, else None."""
    if not isinstance(medications, list):
        return "medications debe ser una lista"
    for med in medications:
        if not isinstance(med, dict) or not med.get("name") or not med.get("dosage"):
            return "Cada medicamento requiere nombre y dosis"
    return None


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

    query = Treatment.query.options(joinedload(Treatment.treatment_plan))
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
            has_prescription:
              type: boolean
              default: false
            medications:
              type: array
              description: >
                Cada medicamento requiere al menos "name" y "dosage". Formato:
                [{name, concentration, form, quantity, dosage, duration}]
              items:
                type: object
            prescription_notes:
              type: string
              description: Indicaciones generales del recetario
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

    medications = data.get("medications") or []
    med_error = _validate_medications(medications)
    if med_error:
        return jsonify({"error": med_error}), 400

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
        has_prescription=bool(data.get("has_prescription", False)),
        medications=medications,
        prescription_notes=data.get("prescription_notes"),
    )

    # Update plan session count if linked. Row-locked so two treatments
    # registered against the same plan concurrently don't both read the same
    # pre-increment count and lose an update.
    if treatment.treatment_plan_id:
        plan = TreatmentPlan.query.filter_by(id=treatment.treatment_plan_id).with_for_update().first()
        if plan:
            plan.completed_sessions += 1

    db.session.add(treatment)
    db.session.commit()

    return jsonify({"treatment": treatment.to_dict(), "message": "Atención registrada correctamente"}), 201


@treatments_bp.route("/<int:treatment_id>", methods=["PUT"])
@doctor_or_admin_required
def update_treatment(treatment_id):
    """
    Actualizar atención
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    description: Solo administrador y médico.
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
            has_prescription:
              type: boolean
            medications:
              type: array
              description: >
                Cada medicamento requiere al menos "name" y "dosage". Formato:
                [{name, concentration, form, quantity, dosage, duration}]
              items:
                type: object
            prescription_notes:
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

    if "medications" in data:
        med_error = _validate_medications(data["medications"] or [])
        if med_error:
            return jsonify({"error": med_error}), 400

    fields = [
        "diagnosis", "procedure", "tooth_number", "tooth_surface",
        "description", "clinical_notes", "prescriptions", "next_steps",
        "has_prescription", "medications", "prescription_notes",
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


# ─── CLINICAL IMAGES ─────────────────────────────────────────────────────────
#
# Photos taken during an appointment (Treatment) or across a whole
# TreatmentPlan. Bytes live in a private Supabase Storage bucket; only metadata
# is stored in `treatment_images`. Every read of the bytes goes through
# get_treatment_image_file() below, which loads the row under the current
# clinic's scope first — so tenant isolation for the image content rides on the
# same ORM-filter + RLS layers as everything else (bucket is never public).

def _read_upload_or_error():
    """Validate the multipart 'file' part; return (bytes, content_type) or an
    (error_response, status) tuple."""
    if not storage.is_configured():
        return None, (jsonify({
            "error": "Almacenamiento de imágenes no configurado (SUPABASE_URL / SUPABASE_SERVICE_KEY)."
        }), 503)

    file = request.files.get("file")
    if file is None or file.filename == "":
        return None, (jsonify({"error": "No se envió ninguna imagen (campo 'file')"}), 400)

    content_type = (file.mimetype or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        return None, (jsonify({"error": "Formato no permitido. Use JPEG, PNG o WEBP."}), 400)

    data = file.read()
    if not data:
        return None, (jsonify({"error": "El archivo está vacío"}), 400)
    if len(data) > MAX_IMAGE_BYTES:
        return None, (jsonify({"error": "La imagen supera el tamaño máximo permitido (8 MB)"}), 400)

    return (data, content_type), None


def _persist_image(*, clinic_id, patient_id, treatment_id, treatment_plan_id,
                   uploaded_by_id, data, content_type, path_prefix, caption):
    """Upload the bytes to storage and create the TreatmentImage row.

    Returns (image, error_response_tuple) — mirrors _read_upload_or_error so
    callers can `return` the error directly instead of leaking an unhandled
    StorageError as a bare 500.
    """
    ext = _EXT_BY_TYPE.get(content_type, "jpg")
    storage_path = f"clinic_{clinic_id}/{path_prefix}/{uuid.uuid4().hex}.{ext}"
    try:
        storage.upload_object(storage_path, data, content_type)
    except storage.StorageError:
        return None, (jsonify({"error": "No se pudo subir la imagen al almacenamiento"}), 502)

    image = TreatmentImage(
        clinic_id=clinic_id,
        patient_id=patient_id,
        treatment_id=treatment_id,
        treatment_plan_id=treatment_plan_id,
        uploaded_by_id=uploaded_by_id,
        storage_path=storage_path,
        content_type=content_type,
        file_size=len(data),
        caption=caption,
    )
    db.session.add(image)
    db.session.commit()
    return image, None


@treatments_bp.route("/<int:treatment_id>/images", methods=["POST"])
@medical_staff_required
def upload_treatment_image(treatment_id):
    """
    Subir una foto a una atención
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    consumes:
      - multipart/form-data
    description: Solo personal médico. La imagen se guarda en almacenamiento privado y solo es accesible para la clínica dueña del paciente.
    parameters:
      - in: path
        name: treatment_id
        type: integer
        required: true
      - in: formData
        name: file
        type: file
        required: true
        description: Imagen JPEG, PNG o WEBP (comprimida en el cliente).
      - in: formData
        name: caption
        type: string
        required: false
    responses:
      201:
        description: Imagen subida
      400:
        description: Archivo inválido
      403:
        description: Acceso denegado
      404:
        description: Atención no encontrada
      503:
        description: Almacenamiento no configurado
    """
    current = get_current_user()
    treatment = Treatment.query.get_or_404(treatment_id, description="Atención no encontrada")

    result, error = _read_upload_or_error()
    if error:
        return error
    data, content_type = result

    image, error = _persist_image(
        clinic_id=treatment.clinic_id,
        patient_id=treatment.patient_id,
        treatment_id=treatment.id,
        treatment_plan_id=treatment.treatment_plan_id,
        uploaded_by_id=current.id,
        data=data,
        content_type=content_type,
        path_prefix=f"treatment_{treatment.id}",
        caption=(request.form.get("caption") or None),
    )
    if error:
        return error
    return jsonify({"image": image.to_dict(), "message": "Imagen subida"}), 201


@treatments_bp.route("/plans/<int:plan_id>/images", methods=["POST"])
@medical_staff_required
def upload_plan_image(plan_id):
    """
    Subir una foto a un plan de tratamiento
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    consumes:
      - multipart/form-data
    description: Solo personal médico. Foto asociada al plan completo (no a una sesión puntual).
    parameters:
      - in: path
        name: plan_id
        type: integer
        required: true
      - in: formData
        name: file
        type: file
        required: true
      - in: formData
        name: caption
        type: string
        required: false
    responses:
      201:
        description: Imagen subida
      400:
        description: Archivo inválido
      403:
        description: Acceso denegado
      404:
        description: Plan no encontrado
      503:
        description: Almacenamiento no configurado
    """
    current = get_current_user()
    plan = TreatmentPlan.query.get_or_404(plan_id, description="Plan no encontrado")

    result, error = _read_upload_or_error()
    if error:
        return error
    data, content_type = result

    image, error = _persist_image(
        clinic_id=plan.clinic_id,
        patient_id=plan.patient_id,
        treatment_id=None,
        treatment_plan_id=plan.id,
        uploaded_by_id=current.id,
        data=data,
        content_type=content_type,
        path_prefix=f"plan_{plan.id}",
        caption=(request.form.get("caption") or None),
    )
    if error:
        return error
    return jsonify({"image": image.to_dict(), "message": "Imagen subida"}), 201


@treatments_bp.route("/<int:treatment_id>/images", methods=["GET"])
@clinical_access_required
def list_treatment_images(treatment_id):
    """
    Listar fotos de una atención
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
        description: Lista de imágenes (más recientes primero)
      403:
        description: Acceso denegado
    """
    images = (TreatmentImage.query
              .filter_by(treatment_id=treatment_id)
              .order_by(TreatmentImage.created_at.desc())
              .all())
    return jsonify({"images": [img.to_dict() for img in images]}), 200


@treatments_bp.route("/plans/<int:plan_id>/images", methods=["GET"])
@clinical_access_required
def list_plan_images(plan_id):
    """
    Listar fotos de un plan de tratamiento (galería completa)
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    description: >
      Incluye tanto las fotos subidas directamente al plan como las de cada
      sesión del plan (toda foto tomada en una atención vinculada al plan
      hereda su treatment_plan_id).
    parameters:
      - in: path
        name: plan_id
        type: integer
        required: true
    responses:
      200:
        description: Lista de imágenes del plan (más recientes primero)
      403:
        description: Acceso denegado
    """
    images = (TreatmentImage.query
              .filter_by(treatment_plan_id=plan_id)
              .order_by(TreatmentImage.created_at.desc())
              .all())
    return jsonify({"images": [img.to_dict() for img in images]}), 200


@treatments_bp.route("/images/<int:image_id>/file", methods=["GET"])
@clinical_access_required
def get_treatment_image_file(image_id):
    """
    Descargar/visualizar los bytes de una imagen clínica
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    description: >
      Sirve la imagen desde el almacenamiento privado. La fila se carga bajo el
      scope de la clínica actual (ORM + RLS), así que una clínica nunca puede
      acceder a las fotos de otra aunque adivine el id.
    produces:
      - image/jpeg
      - image/png
      - image/webp
    parameters:
      - in: path
        name: image_id
        type: integer
        required: true
    responses:
      200:
        description: Bytes de la imagen
      404:
        description: Imagen no encontrada
      503:
        description: Almacenamiento no configurado
    """
    if not storage.is_configured():
        return jsonify({"error": "Almacenamiento de imágenes no configurado."}), 503

    image = TreatmentImage.query.get_or_404(image_id, description="Imagen no encontrada")
    try:
        data = storage.download_object(image.storage_path)
    except storage.StorageError:
        return jsonify({"error": "No se pudo recuperar la imagen del almacenamiento"}), 502

    return Response(
        data,
        mimetype=image.content_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@treatments_bp.route("/images/<int:image_id>", methods=["DELETE"])
@medical_staff_required
def delete_treatment_image(image_id):
    """
    Eliminar una imagen clínica
    ---
    tags:
      - Atenciones
    security:
      - BearerAuth: []
    description: Solo personal médico. Elimina el objeto del almacenamiento y su registro.
    parameters:
      - in: path
        name: image_id
        type: integer
        required: true
    responses:
      200:
        description: Imagen eliminada
      403:
        description: Acceso denegado
      404:
        description: Imagen no encontrada
    """
    image = TreatmentImage.query.get_or_404(image_id, description="Imagen no encontrada")

    # Best-effort remove from the bucket first; a 404 there is treated as
    # success. If storage is unreachable we keep the row so we don't orphan the
    # object silently.
    if storage.is_configured():
        try:
            storage.delete_object(image.storage_path)
        except storage.StorageError:
            return jsonify({"error": "No se pudo eliminar la imagen del almacenamiento"}), 502

    db.session.delete(image)
    db.session.commit()
    return jsonify({"message": "Imagen eliminada"}), 200
