from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from app.models.user import User
from app.middleware.auth import require_auth, get_current_user
from app.middleware.tenancy import platform_wide_lookup

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Iniciar sesión
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [email, password]
          properties:
            email:
              type: string
              example: admin@clinica.com
            password:
              type: string
              example: Admin2025!
    responses:
      200:
        description: Login exitoso
        schema:
          type: object
          properties:
            access_token:
              type: string
            refresh_token:
              type: string
            user:
              $ref: '#/definitions/User'
      400:
        description: Datos requeridos / incompletos
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Credenciales incorrectas
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Usuario inactivo
        schema:
          $ref: '#/definitions/Error'
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Datos requeridos"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email y contraseña requeridos"}), 400

    # Email is unique platform-wide; never scope a login lookup to any one clinic.
    with platform_wide_lookup():
        user = User.query.filter_by(email=email).execution_options(skip_clinic_filter=True).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Credenciales incorrectas"}), 401

    if not user.is_active:
        return jsonify({"error": "Usuario inactivo. Contacte al administrador"}), 403

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict()
    }), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Renovar token de acceso
    ---
    tags:
      - Auth
    security:
      - BearerAuth: []
    description: Requiere un *refresh token* válido (obtenido en el login) en el header Authorization.
    responses:
      200:
        description: Nuevo access token generado
        schema:
          type: object
          properties:
            access_token:
              type: string
      401:
        description: Usuario no válido o token inválido
        schema:
          $ref: '#/definitions/Error'
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return jsonify({"error": "Usuario no válido"}), 401
    new_token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": new_token}), 200


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    """
    Obtener usuario autenticado
    ---
    tags:
      - Auth
    security:
      - BearerAuth: []
    responses:
      200:
        description: Datos del usuario autenticado
        schema:
          type: object
          properties:
            user:
              $ref: '#/definitions/User'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
    """
    user = get_current_user()
    return jsonify({"user": user.to_dict()}), 200


@auth_bp.route("/change-password", methods=["PUT"])
@require_auth
def change_password():
    """
    Cambiar contraseña
    ---
    tags:
      - Auth
    security:
      - BearerAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [current_password, new_password]
          properties:
            current_password:
              type: string
              example: Admin2025!
            new_password:
              type: string
              example: NuevaClave2026!
              minLength: 8
    responses:
      200:
        description: Contraseña actualizada correctamente
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: Datos faltantes, contraseña muy corta o contraseña actual incorrecta
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
    """
    user = get_current_user()
    data = request.get_json()

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "Contraseña actual y nueva son requeridas"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "La nueva contraseña debe tener al menos 8 caracteres"}), 400

    if not user.check_password(current_password):
        return jsonify({"error": "Contraseña actual incorrecta"}), 400

    user.set_password(new_password)
    from app import db
    db.session.commit()

    return jsonify({"message": "Contraseña actualizada correctamente"}), 200
