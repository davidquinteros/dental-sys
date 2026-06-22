import re
import unicodedata
from flask import Blueprint, request, jsonify
from app import db
from app.models.appointment_type import AppointmentTypeCatalog
from app.middleware.auth import clinical_access_required, get_current_user
from app.models.user import UserRole

appointment_types_bp = Blueprint("appointment_types", __name__)


def _slugify(text: str) -> str:
    """Convert a label to a safe key string."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')[:50]


@appointment_types_bp.route("/", methods=["GET"])
@clinical_access_required
def list_types():
    types = (AppointmentTypeCatalog.query
             .filter_by(is_active=True)
             .order_by(AppointmentTypeCatalog.sort_order)
             .all())
    return jsonify({"appointment_types": [t.to_dict() for t in types]}), 200


@appointment_types_bp.route("/all", methods=["GET"])
@clinical_access_required
def list_all_types():
    """Includes inactive, for admin CRUD page."""
    current = get_current_user()
    if current.role != UserRole.ADMIN:
        return jsonify({"error": "Solo el administrador puede ver todos los tipos"}), 403
    types = (AppointmentTypeCatalog.query
             .order_by(AppointmentTypeCatalog.sort_order)
             .all())
    return jsonify({"appointment_types": [t.to_dict() for t in types]}), 200


@appointment_types_bp.route("/", methods=["POST"])
@clinical_access_required
def create_type():
    current = get_current_user()
    if current.role != UserRole.ADMIN:
        return jsonify({"error": "Solo el administrador puede crear tipos de cita"}), 403

    data = request.get_json() or {}
    label = (data.get("label") or "").strip()
    if not label:
        return jsonify({"error": "El nombre del tipo es requerido"}), 400

    # Auto-generate unique key from label
    base_key = _slugify(label)
    key = base_key
    n = 1
    while AppointmentTypeCatalog.query.filter_by(key=key).first():
        key = f"{base_key}_{n}"
        n += 1

    t = AppointmentTypeCatalog(
        clinic_id=current.clinic_id,
        key=key,
        label=label,
        color=data.get("color", "#4299e1"),
        sort_order=data.get("sort_order", 200),
    )
    db.session.add(t)
    db.session.commit()
    return jsonify({"appointment_type": t.to_dict(), "message": "Tipo creado"}), 201


@appointment_types_bp.route("/<int:tid>", methods=["PUT"])
@clinical_access_required
def update_type(tid):
    current = get_current_user()
    if current.role != UserRole.ADMIN:
        return jsonify({"error": "Solo el administrador puede modificar tipos de cita"}), 403

    t = AppointmentTypeCatalog.query.get_or_404(tid, description="Tipo no encontrado")
    if not t.is_active:
        return jsonify({"error": "No se puede modificar un tipo de cita inactivo. Reactívelo primero."}), 400

    data = request.get_json() or {}
    for field in ["label", "color", "sort_order"]:
        if field in data:
            setattr(t, field, data[field])
    db.session.commit()
    return jsonify({"appointment_type": t.to_dict(), "message": "Tipo actualizado"}), 200


@appointment_types_bp.route("/<int:tid>", methods=["DELETE"])
@clinical_access_required
def delete_type(tid):
    current = get_current_user()
    if current.role != UserRole.ADMIN:
        return jsonify({"error": "Solo el administrador puede desactivar tipos de cita"}), 403

    t = AppointmentTypeCatalog.query.get_or_404(tid, description="Tipo no encontrado")
    t.is_active = False
    db.session.commit()
    return jsonify({"message": "Tipo desactivado"}), 200


@appointment_types_bp.route("/<int:tid>/activate", methods=["PUT"])
@clinical_access_required
def activate_type(tid):
    current = get_current_user()
    if current.role != UserRole.ADMIN:
        return jsonify({"error": "Solo el administrador puede reactivar tipos de cita"}), 403

    t = AppointmentTypeCatalog.query.get_or_404(tid, description="Tipo no encontrado")
    t.is_active = True
    db.session.commit()
    return jsonify({"appointment_type": t.to_dict(), "message": "Tipo reactivado"}), 200
