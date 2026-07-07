from flask import Blueprint, request, jsonify
from app import db
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.user import User, UserRole
from app.middleware.auth import clinical_access_required, get_current_user
from app.utils.clinic_time import local_now, local_today
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload

appointments_bp = Blueprint("appointments", __name__)


def check_consultorio_availability(consultorio_id: int, scheduled_at: datetime, duration: int, exclude_id: int = None) -> bool:
    """Check if a consultorio (room) is free at the given time slot"""
    if not consultorio_id:
        return True
    end_time = scheduled_at + timedelta(minutes=duration)
    day_start = datetime.combine(scheduled_at.date(), datetime.min.time())
    day_end = datetime.combine(scheduled_at.date(), datetime.max.time())

    query = Appointment.query.filter(
        Appointment.consultorio_id == consultorio_id,
        Appointment.status.not_in([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW, AppointmentStatus.COMPLETED]),
        Appointment.scheduled_at >= day_start,
        Appointment.scheduled_at <= day_end,
    )
    if exclude_id:
        query = query.filter(Appointment.id != exclude_id)

    for existing in query.all():
        existing_end = existing.scheduled_at + timedelta(minutes=existing.duration_minutes)
        if scheduled_at < existing_end and existing.scheduled_at < end_time:
            return False
    return True


def check_doctor_availability(doctor_id: int, scheduled_at: datetime, duration: int, exclude_id: int = None) -> bool:
    """Check if a doctor is available at a given time slot"""
    end_time = scheduled_at + timedelta(minutes=duration)
    day_start = datetime.combine(scheduled_at.date(), datetime.min.time())
    day_end = datetime.combine(scheduled_at.date(), datetime.max.time())

    query = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status.not_in([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW, AppointmentStatus.COMPLETED]),
        Appointment.scheduled_at >= day_start,
        Appointment.scheduled_at <= day_end,
    )
    if exclude_id:
        query = query.filter(Appointment.id != exclude_id)

    for existing in query.all():
        existing_end = existing.scheduled_at + timedelta(minutes=existing.duration_minutes)
        if scheduled_at < existing_end and existing.scheduled_at < end_time:
            return False
    return True


@appointments_bp.route("/", methods=["GET"])
@clinical_access_required
def list_appointments():
    """
    Listar citas
    ---
    tags:
      - Citas
    security:
      - BearerAuth: []
    description: >
      Los médicos solo ven sus propias citas. Asistentes pueden filtrar por médico.
      Administradores y recepción ven todas las citas y pueden filtrar por médico.
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
      - in: query
        name: per_page
        type: integer
        default: 30
      - in: query
        name: doctor_id
        type: integer
      - in: query
        name: patient_id
        type: integer
      - in: query
        name: status
        type: string
        enum: [scheduled, confirmed, in_progress, completed, cancelled, no_show]
      - in: query
        name: date_from
        type: string
        format: date-time
        description: ISO 8601 (ej. 2026-06-01T00:00:00)
      - in: query
        name: date_to
        type: string
        format: date-time
        description: ISO 8601 (ej. 2026-06-30T23:59:59)
      - in: query
        name: all
        type: boolean
        description: >
          Si es true, un médico ve las citas de todos los médicos (para
          coordinar la agenda del consultorio) en lugar de solo las suyas.
    responses:
      200:
        description: Lista paginada de citas
        schema:
          type: object
          properties:
            appointments:
              type: array
              items:
                $ref: '#/definitions/Appointment'
            total:
              type: integer
            pages:
              type: integer
            current_page:
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
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 30, type=int)
    doctor_id = request.args.get("doctor_id", type=int)
    patient_id = request.args.get("patient_id", type=int)
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    show_all = request.args.get("all", "").lower() in ("true", "1")

    query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
    )

    # Doctors only see their own appointments unless admin/receptionist,
    # or unless they explicitly request the shared clinic agenda (all=true)
    if current.role == UserRole.DOCTOR and not show_all:
        query = query.filter_by(doctor_id=current.id)
    elif current.role == UserRole.ASSISTANT:
        query = query.filter_by(doctor_id=doctor_id) if doctor_id else query
    else:
        if doctor_id:
            query = query.filter_by(doctor_id=doctor_id)

    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if status:
        query = query.filter_by(status=status)
    if date_from:
        try:
            query = query.filter(Appointment.scheduled_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Appointment.scheduled_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    pagination = query.order_by(Appointment.scheduled_at).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "appointments": [a.to_dict() for a in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    }), 200


@appointments_bp.route("/<int:appt_id>", methods=["GET"])
@clinical_access_required
def get_appointment(appt_id):
    """
    Obtener cita por ID
    ---
    tags:
      - Citas
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: appt_id
        type: integer
        required: true
    responses:
      200:
        description: Datos de la cita
        schema:
          type: object
          properties:
            appointment:
              $ref: '#/definitions/Appointment'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Cita no encontrada
        schema:
          $ref: '#/definitions/Error'
    """
    appt = Appointment.query.get_or_404(appt_id, description="Cita no encontrada")
    return jsonify({"appointment": appt.to_dict()}), 200


@appointments_bp.route("/", methods=["POST"])
@clinical_access_required
def create_appointment():
    """
    Agendar cita
    ---
    tags:
      - Citas
    security:
      - BearerAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [patient_id, doctor_id, scheduled_at, appointment_type]
          properties:
            patient_id:
              type: integer
              example: 3
            doctor_id:
              type: integer
              example: 2
            scheduled_at:
              type: string
              format: date-time
              example: "2026-06-20T09:00:00"
              description: Formato ISO 8601, no puede ser una fecha en el pasado
            appointment_type:
              type: string
              enum: [consultation, cleaning, extraction, filling, endodontics, orthodontics, implant, whitening, crown, followup, other]
              example: consultation
            duration_minutes:
              type: integer
              default: 30
              example: 30
            treatment_plan_id:
              type: integer
              description: ID del plan de tratamiento, si la cita es parte de uno
            session_number:
              type: integer
              description: Número de sesión dentro del plan
            reason:
              type: string
              example: Dolor en muela
            notes:
              type: string
    responses:
      201:
        description: Cita registrada correctamente
        schema:
          type: object
          properties:
            appointment:
              $ref: '#/definitions/Appointment'
            message:
              type: string
      400:
        description: Campo requerido faltante, fecha inválida, en el pasado, o tipo de cita inválido
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
        description: Médico no encontrado o inactivo
        schema:
          $ref: '#/definitions/Error'
      409:
        description: El médico no está disponible en ese horario
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    data = request.get_json()
    required = ["patient_id", "doctor_id", "scheduled_at", "appointment_type"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    try:
        scheduled_at = datetime.fromisoformat(data["scheduled_at"])
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Use ISO 8601"}), 400

    if scheduled_at < local_now():
        return jsonify({"error": "No se puede agendar en el pasado"}), 400

    from app.models.appointment_type import AppointmentTypeCatalog
    appt_type_key = (data.get("appointment_type") or "").strip()
    if not appt_type_key or not AppointmentTypeCatalog.query.filter_by(key=appt_type_key, is_active=True).first():
        return jsonify({"error": "Tipo de cita inválido"}), 400

    duration = int(data.get("duration_minutes", 30))
    doctor = User.query.filter_by(id=data["doctor_id"], role=UserRole.DOCTOR, is_active=True).first()
    if not doctor:
        return jsonify({"error": "Médico no encontrado o inactivo"}), 404

    if not check_doctor_availability(data["doctor_id"], scheduled_at, duration):
        return jsonify({"error": "El médico no está disponible en ese horario"}), 409

    consultorio_id = data.get("consultorio_id") or None
    if consultorio_id and not check_consultorio_availability(consultorio_id, scheduled_at, duration):
        return jsonify({"error": "El consultorio ya está ocupado en ese horario"}), 409

    appointment = Appointment(
        clinic_id=current.clinic_id,
        patient_id=data["patient_id"],
        doctor_id=data["doctor_id"],
        consultorio_id=consultorio_id,
        created_by_id=current.id,
        scheduled_at=scheduled_at,
        duration_minutes=duration,
        appointment_type=appt_type_key,
        treatment_plan_id=data.get("treatment_plan_id"),
        session_number=data.get("session_number"),
        reason=data.get("reason"),
        notes=data.get("notes"),
    )

    db.session.add(appointment)
    db.session.commit()

    return jsonify({"appointment": appointment.to_dict(), "message": "Cita registrada correctamente"}), 201


@appointments_bp.route("/<int:appt_id>", methods=["PUT"])
@clinical_access_required
def update_appointment(appt_id):
    """
    Actualizar cita
    ---
    tags:
      - Citas
    security:
      - BearerAuth: []
    description: El estado siempre puede modificarse; los demás campos no son editables si la cita ya está completada o cancelada.
    parameters:
      - in: path
        name: appt_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            scheduled_at:
              type: string
              format: date-time
              description: Reprograma la cita; valida disponibilidad del médico
            duration_minutes:
              type: integer
            reason:
              type: string
            notes:
              type: string
            session_number:
              type: integer
            treatment_plan_id:
              type: integer
              description: Plan de tratamiento asociado. Enviar null para desasociar.
            status:
              type: string
              enum: [scheduled, confirmed, in_progress, completed, cancelled, no_show]
              description: Si se marca 'completed', se registra automáticamente completed_at
            cancellation_reason:
              type: string
    responses:
      200:
        description: Cita actualizada
        schema:
          type: object
          properties:
            appointment:
              $ref: '#/definitions/Appointment'
            message:
              type: string
      400:
        description: Campo no editable en cita completada/cancelada, fecha o estado inválido
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
        description: Cita no encontrada
        schema:
          $ref: '#/definitions/Error'
      409:
        description: El médico no está disponible en el nuevo horario
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    appt = Appointment.query.get_or_404(appt_id, description="Cita no encontrada")
    data = request.get_json()

    # El estado (y su motivo de cancelación) siempre puede cambiarse; el resto de
    # los campos quedan congelados una vez que la cita está completada/cancelada.
    locked = appt.status in [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED]
    editable_fields = {"scheduled_at", "consultorio_id", "duration_minutes", "reason", "notes", "session_number", "treatment_plan_id"}
    if locked and editable_fields.intersection(data.keys()):
        return jsonify({"error": "No se puede modificar una cita completada o cancelada"}), 400

    if "scheduled_at" in data:
        try:
            new_time = datetime.fromisoformat(data["scheduled_at"])
            duration = int(data.get("duration_minutes", appt.duration_minutes))
            if not check_doctor_availability(appt.doctor_id, new_time, duration, exclude_id=appt_id):
                return jsonify({"error": "El médico no está disponible en ese horario"}), 409
            new_consultorio = data.get("consultorio_id", appt.consultorio_id)
            if new_consultorio and not check_consultorio_availability(new_consultorio, new_time, duration, exclude_id=appt_id):
                return jsonify({"error": "El consultorio ya está ocupado en ese horario"}), 409
            appt.scheduled_at = new_time
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido"}), 400

    if "consultorio_id" in data:
        appt.consultorio_id = data["consultorio_id"] or None

    for field in ["duration_minutes", "reason", "notes", "session_number", "treatment_plan_id"]:
        if field in data:
            setattr(appt, field, data[field])

    if "status" in data:
        try:
            new_status = AppointmentStatus(data["status"])
            appt.status = new_status
            appt.completed_at = local_now() if new_status == AppointmentStatus.COMPLETED else None
        except ValueError:
            return jsonify({"error": "Estado inválido"}), 400

    if "cancellation_reason" in data:
        appt.cancellation_reason = data["cancellation_reason"]

    db.session.commit()
    return jsonify({"appointment": appt.to_dict(), "message": "Cita actualizada"}), 200


@appointments_bp.route("/<int:appt_id>/cancel", methods=["POST"])
@clinical_access_required
def cancel_appointment(appt_id):
    """
    Cancelar cita
    ---
    tags:
      - Citas
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: appt_id
        type: integer
        required: true
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            reason:
              type: string
              example: Paciente solicitó reprogramar
    responses:
      200:
        description: Cita cancelada
        schema:
          type: object
          properties:
            message:
              type: string
            appointment:
              $ref: '#/definitions/Appointment'
      400:
        description: No se puede cancelar una cita completada
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
        description: Cita no encontrada
        schema:
          $ref: '#/definitions/Error'
    """
    appt = Appointment.query.get_or_404(appt_id)
    data = request.get_json() or {}

    if appt.status == AppointmentStatus.COMPLETED:
        return jsonify({"error": "No se puede cancelar una cita completada"}), 400

    appt.status = AppointmentStatus.CANCELLED
    appt.cancellation_reason = data.get("reason", "Cancelada sin motivo especificado")
    db.session.commit()
    return jsonify({"message": "Cita cancelada", "appointment": appt.to_dict()}), 200


@appointments_bp.route("/availability", methods=["GET"])
@clinical_access_required
def check_availability():
    """
    Consultar disponibilidad de un médico
    ---
    tags:
      - Citas
    security:
      - BearerAuth: []
    description: Devuelve los horarios ya ocupados de un médico en una fecha determinada.
    parameters:
      - in: query
        name: doctor_id
        type: integer
        required: true
      - in: query
        name: date
        type: string
        format: date
        required: true
        example: "2026-06-20"
    responses:
      200:
        description: Horarios ocupados del médico en la fecha solicitada
        schema:
          type: object
          properties:
            doctor_id:
              type: integer
            date:
              type: string
            booked_slots:
              type: array
              items:
                type: object
                properties:
                  start:
                    type: string
                    format: date-time
                  end:
                    type: string
                    format: date-time
                  appointment_id:
                    type: integer
      400:
        description: Parámetros faltantes o fecha inválida
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
    doctor_id = request.args.get("doctor_id", type=int)
    date_str = request.args.get("date")

    if not doctor_id or not date_str:
        return jsonify({"error": "doctor_id y date son requeridos"}), 400

    try:
        target_date = datetime.fromisoformat(date_str).date()
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido"}), 400

    # Get all appointments for that doctor on that day
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())

    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.scheduled_at >= day_start,
        Appointment.scheduled_at <= day_end,
        Appointment.status.not_in([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW, AppointmentStatus.COMPLETED]),
    ).order_by(Appointment.scheduled_at).all()

    return jsonify({
        "doctor_id": doctor_id,
        "date": date_str,
        "booked_slots": [
            {
                "start": a.scheduled_at.isoformat(),
                "end": (a.scheduled_at + timedelta(minutes=a.duration_minutes)).isoformat(),
                "appointment_id": a.id,
            }
            for a in appointments
        ],
    }), 200


@appointments_bp.route("/today", methods=["GET"])
@clinical_access_required
def today_appointments():
    """
    Citas de hoy
    ---
    tags:
      - Citas
    security:
      - BearerAuth: []
    description: Lista rápida de las citas del día actual. Los médicos solo ven las suyas.
    responses:
      200:
        description: Citas de hoy
        schema:
          type: object
          properties:
            appointments:
              type: array
              items:
                $ref: '#/definitions/Appointment'
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
    current = get_current_user()
    today = local_today()
    day_start = datetime.combine(today, datetime.min.time())
    day_end = datetime.combine(today, datetime.max.time())

    query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
    ).filter(
        Appointment.scheduled_at >= day_start,
        Appointment.scheduled_at <= day_end,
    )
    if current.role == UserRole.DOCTOR:
        query = query.filter_by(doctor_id=current.id)

    appointments = query.order_by(Appointment.scheduled_at).all()
    return jsonify({"appointments": [a.to_dict() for a in appointments], "total": len(appointments)}), 200
