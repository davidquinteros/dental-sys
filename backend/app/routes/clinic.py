from flask import Blueprint, jsonify, Response
from app.middleware.auth import clinical_access_required, get_current_user
from app.models.clinic import Clinic
from app.utils import storage

clinic_bp = Blueprint("clinic", __name__)


def _serve_clinic_logo(clinic):
    """Stream a clinic's logo bytes from private storage, or a JSON error tuple.
    Shared by the self-scoped /clinic/logo route and the id-scoped
    /platform/clinics/<id>/logo route."""
    if not clinic.logo_url:
        return jsonify({"error": "Esta clínica no tiene logo"}), 404
    if not storage.is_configured():
        return jsonify({"error": "Almacenamiento de imágenes no configurado."}), 503
    try:
        data = storage.download_object(clinic.logo_url)
    except storage.StorageError:
        return jsonify({"error": "No se pudo recuperar el logo del almacenamiento"}), 502
    return Response(
        data,
        mimetype="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@clinic_bp.route("/info", methods=["GET"])
@clinical_access_required
def clinic_info():
    """
    Datos públicos de la clínica del usuario autenticado
    ---
    tags:
      - Clínica
    security:
      - BearerAuth: []
    description: >
      Devuelve solo los datos de encabezado (nombre, dirección, teléfono, logo) de la
      clínica del usuario autenticado — no expone estado de suscripción/facturación,
      que es exclusivo de /api/platform/*.
    responses:
      200:
        description: Datos de la clínica
        schema:
          type: object
          properties:
            name:
              type: string
            address:
              type: string
            phone:
              type: string
            logo_url:
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
        description: Usuario sin clínica asignada
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    clinic = Clinic.query.get_or_404(current.clinic_id, description="Clínica no encontrada")
    return jsonify({
        "name": clinic.name,
        "address": clinic.address,
        "phone": clinic.phone,
        "logo_url": clinic.logo_url,
    }), 200


@clinic_bp.route("/logo", methods=["GET"])
@clinical_access_required
def clinic_logo():
    """
    Logo de la clínica del usuario autenticado
    ---
    tags:
      - Clínica
    security:
      - BearerAuth: []
    produces:
      - image/jpeg
    responses:
      200:
        description: Bytes del logo
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Usuario sin clínica asignada, o clínica sin logo
        schema:
          $ref: '#/definitions/Error'
      503:
        description: Almacenamiento no configurado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    if not current.clinic_id:
        return jsonify({"error": "Usuario sin clínica asignada"}), 404
    clinic = Clinic.query.get_or_404(current.clinic_id, description="Clínica no encontrada")
    return _serve_clinic_logo(clinic)
