from flask import Blueprint, jsonify, Response, request
from app import db
from app.middleware.auth import clinical_access_required, admin_required, get_current_user
from app.models.clinic import Clinic
from app.utils import storage
from app.routes.treatments import _read_upload_or_error

clinic_bp = Blueprint("clinic", __name__)

# Fixed per-clinic storage paths. The print path stays `logo.jpg` (FCLI-8's original
# path) so logos already uploaded before the split are not orphaned; `logo_main.jpg`
# is new (FCLI-19). Both live in the same private bucket as clinical photos.
_LOGO_PATHS = {
    "main": lambda clinic_id: f"clinic_{clinic_id}/logo_main.jpg",
    "print": lambda clinic_id: f"clinic_{clinic_id}/logo.jpg",
}


def _serve_clinic_logo(clinic, storage_path, cacheable: bool = True):
    """Stream a clinic's logo bytes from private storage, or a JSON error tuple.
    Shared by the self-scoped /clinic/logo/<kind> routes and the id-scoped
    /platform/clinics/<id>/logo/<kind> routes.

    `storage_path` is the internal bucket path to serve (the caller picks main vs
    print). `cacheable` controls whether the browser may cache under `max-age`:
    the id-scoped platform route embeds the clinic id in the URL, so per-clinic
    caching is safe there. The self-scoped route's URL is constant regardless of
    which clinic the authenticated user belongs to — caching it would let a
    browser serve one clinic's logo to a different clinic's user on a shared
    browser profile, so it must pass `cacheable=False`."""
    if not storage_path:
        return jsonify({"error": "Esta clínica no tiene logo"}), 404
    if not storage.is_configured():
        return jsonify({"error": "Almacenamiento de imágenes no configurado."}), 503
    try:
        data = storage.download_object(storage_path)
    except storage.StorageError:
        return jsonify({"error": "No se pudo recuperar el logo del almacenamiento"}), 502
    cache_control = "private, max-age=3600" if cacheable else "private, no-store"
    return Response(
        data,
        mimetype="image/jpeg",
        headers={"Cache-Control": cache_control},
    )


@clinic_bp.route("/info", methods=["GET"])
@clinical_access_required
def clinic_info():
    """
    Datos de perfil de la clínica del usuario autenticado
    ---
    tags:
      - Clínica
    security:
      - BearerAuth: []
    description: >
      Devuelve solo los datos de perfil (nombre, dirección, teléfono, email, logos) de
      la clínica del usuario autenticado — no expone estado de suscripción/facturación,
      que es exclusivo de /api/platform/*. Los campos de logo devuelven la ruta del
      endpoint que sirve cada imagen si la clínica tiene ese logo cargado, o `null`.
    responses:
      200:
        description: Datos de la clínica
        schema:
          type: object
          properties:
            name: {type: string}
            address: {type: string}
            phone: {type: string}
            email: {type: string}
            logo_main_url: {type: string}
            logo_print_url: {type: string}
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
        "email": clinic.email,
        # Endpoint route (not the internal storage path) when the logo exists, else null.
        "logo_main_url": "/api/clinic/logo/main" if clinic.logo_main_url else None,
        "logo_print_url": "/api/clinic/logo/print" if clinic.logo_print_url else None,
    }), 200


@clinic_bp.route("/profile", methods=["PUT"])
@admin_required
def update_clinic_profile():
    """
    Editar el perfil de contacto de la propia clínica (solo admin)
    ---
    tags:
      - Clínica
    security:
      - BearerAuth: []
    description: >
      Permite al admin de la propia clínica editar sus datos de contacto. Whitelist
      explícita: solo `address`, `phone`, `email`. El nombre/slug y los campos de
      suscripción NO son editables desde aquí (exclusivos de /api/platform/*), aunque
      vengan en el payload.
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            address: {type: string}
            phone: {type: string}
            email: {type: string}
    responses:
      200:
        description: Perfil actualizado
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado (no admin)
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Usuario sin clínica asignada
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    clinic = Clinic.query.get_or_404(current.clinic_id, description="Clínica no encontrada")
    data = request.get_json(silent=True) or {}

    # Explicit whitelist — never read name/slug/subscription fields from the payload.
    for field in ("address", "phone", "email"):
        if field in data:
            value = data[field]
            setattr(clinic, field, value.strip() if isinstance(value, str) else value)

    db.session.commit()
    return jsonify({
        "name": clinic.name,
        "address": clinic.address,
        "phone": clinic.phone,
        "email": clinic.email,
        "logo_main_url": "/api/clinic/logo/main" if clinic.logo_main_url else None,
        "logo_print_url": "/api/clinic/logo/print" if clinic.logo_print_url else None,
    }), 200


@clinic_bp.route("/logo/<kind>", methods=["GET"])
@clinical_access_required
def clinic_logo(kind):
    """
    Logo (main | print) de la clínica del usuario autenticado
    ---
    tags:
      - Clínica
    security:
      - BearerAuth: []
    produces:
      - image/jpeg
    parameters:
      - in: path
        name: kind
        type: string
        enum: [main, print]
        required: true
    responses:
      200:
        description: Bytes del logo
      400:
        description: Tipo de logo inválido
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Usuario sin clínica asignada, o clínica sin ese logo
        schema:
          $ref: '#/definitions/Error'
      503:
        description: Almacenamiento no configurado
        schema:
          $ref: '#/definitions/Error'
    """
    if kind not in _LOGO_PATHS:
        return jsonify({"error": "Tipo de logo inválido (use 'main' o 'print')"}), 400
    current = get_current_user()
    if not current.clinic_id:
        return jsonify({"error": "Usuario sin clínica asignada"}), 404
    clinic = Clinic.query.get_or_404(current.clinic_id, description="Clínica no encontrada")
    stored = clinic.logo_main_url if kind == "main" else clinic.logo_print_url
    # Self-scoped: URL is constant per user, so it must not be cached (see helper docstring).
    return _serve_clinic_logo(clinic, stored, cacheable=False)


@clinic_bp.route("/logo/<kind>", methods=["POST"])
@admin_required
def upload_clinic_logo(kind):
    """
    Subir el logo (main | print) de la propia clínica (solo admin)
    ---
    tags:
      - Clínica
    security:
      - BearerAuth: []
    consumes:
      - multipart/form-data
    description: >
      Reemplaza el logo indicado (main o print) de la propia clínica. Se guarda en una
      ruta fija por clínica — subir uno nuevo pisa al anterior, sin huérfanos.
    parameters:
      - in: path
        name: kind
        type: string
        enum: [main, print]
        required: true
      - in: formData
        name: file
        type: file
        required: true
        description: Imagen JPEG, PNG o WEBP (comprimida en el cliente).
    responses:
      200:
        description: Logo actualizado
      400:
        description: Archivo o tipo inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado (no admin)
        schema:
          $ref: '#/definitions/Error'
      503:
        description: Almacenamiento no configurado
        schema:
          $ref: '#/definitions/Error'
    """
    if kind not in _LOGO_PATHS:
        return jsonify({"error": "Tipo de logo inválido (use 'main' o 'print')"}), 400
    current = get_current_user()
    clinic = Clinic.query.get_or_404(current.clinic_id, description="Clínica no encontrada")

    result, error = _read_upload_or_error()
    if error:
        return error
    data, content_type = result

    storage_path = _LOGO_PATHS[kind](clinic.id)
    try:
        storage.upload_object(storage_path, data, content_type)
    except storage.StorageError:
        return jsonify({"error": "No se pudo subir el logo al almacenamiento"}), 502

    if kind == "main":
        clinic.logo_main_url = storage_path
    else:
        clinic.logo_print_url = storage_path
    db.session.commit()

    return jsonify({
        "message": "Logo actualizado",
        "logo_main_url": "/api/clinic/logo/main" if clinic.logo_main_url else None,
        "logo_print_url": "/api/clinic/logo/print" if clinic.logo_print_url else None,
    }), 200
