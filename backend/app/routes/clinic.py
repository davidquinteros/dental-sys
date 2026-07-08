from flask import Blueprint, jsonify
from app.middleware.auth import clinical_access_required, get_current_user
from app.models.clinic import Clinic

clinic_bp = Blueprint("clinic", __name__)


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
