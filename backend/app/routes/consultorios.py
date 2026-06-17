from flask import Blueprint, request, jsonify
from app import db
from app.models.consultorio import Consultorio
from app.models.appointment import Appointment, AppointmentStatus
from app.middleware.auth import clinical_access_required, get_current_user
from app.models.user import UserRole
from datetime import datetime, timedelta

consultorios_bp = Blueprint("consultorios", __name__)


@consultorios_bp.route("/", methods=["GET"])
@clinical_access_required
def list_consultorios():
    """Lista todos los consultorios activos"""
    consultorios = Consultorio.query.filter_by(is_active=True).order_by(Consultorio.name).all()
    return jsonify({"consultorios": [c.to_dict() for c in consultorios]}), 200


@consultorios_bp.route("/", methods=["POST"])
@clinical_access_required
def create_consultorio():
    """Crear consultorio (solo admin)"""
    current = get_current_user()
    if current.role != UserRole.ADMIN:
        return jsonify({"error": "Solo el administrador puede crear consultorios"}), 403

    data = request.get_json()
    if not data.get("name", "").strip():
        return jsonify({"error": "El nombre del consultorio es requerido"}), 400

    c = Consultorio(
        name=data["name"].strip(),
        description=data.get("description", "").strip() or None,
        color=data.get("color", "#4299e1"),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"consultorio": c.to_dict(), "message": "Consultorio creado"}), 201


@consultorios_bp.route("/<int:cid>", methods=["PUT"])
@clinical_access_required
def update_consultorio(cid):
    """Actualizar consultorio (solo admin)"""
    current = get_current_user()
    if current.role != UserRole.ADMIN:
        return jsonify({"error": "Solo el administrador puede modificar consultorios"}), 403

    c = Consultorio.query.get_or_404(cid, description="Consultorio no encontrado")
    data = request.get_json()

    for field in ["name", "description", "color"]:
        if field in data:
            setattr(c, field, data[field])

    db.session.commit()
    return jsonify({"consultorio": c.to_dict(), "message": "Consultorio actualizado"}), 200


@consultorios_bp.route("/<int:cid>", methods=["DELETE"])
@clinical_access_required
def delete_consultorio(cid):
    """Desactivar consultorio (solo admin)"""
    current = get_current_user()
    if current.role != UserRole.ADMIN:
        return jsonify({"error": "Solo el administrador puede eliminar consultorios"}), 403

    c = Consultorio.query.get_or_404(cid, description="Consultorio no encontrado")
    c.is_active = False
    db.session.commit()
    return jsonify({"message": "Consultorio desactivado"}), 200


@consultorios_bp.route("/<int:cid>/booked", methods=["GET"])
@clinical_access_required
def consultorio_booked_slots(cid):
    """Horarios ocupados de un consultorio en una fecha"""
    date_str = request.args.get("date")
    exclude_id = request.args.get("exclude_id", type=int)

    if not date_str:
        return jsonify({"error": "date es requerido"}), 400

    try:
        target_date = datetime.fromisoformat(date_str).date()
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido"}), 400

    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())

    query = Appointment.query.filter(
        Appointment.consultorio_id == cid,
        Appointment.scheduled_at >= day_start,
        Appointment.scheduled_at <= day_end,
        Appointment.status.not_in([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
    )
    if exclude_id:
        query = query.filter(Appointment.id != exclude_id)

    slots = query.all()
    return jsonify({
        "booked_slots": [
            {
                "start": a.scheduled_at.isoformat(),
                "end": (a.scheduled_at + timedelta(minutes=a.duration_minutes)).isoformat(),
                "appointment_id": a.id,
                "doctor_name": a.doctor.full_name if a.doctor else None,
            }
            for a in slots
        ],
    }), 200
