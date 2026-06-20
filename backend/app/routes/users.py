from flask import Blueprint, request, jsonify
from app import db
from app.models.user import User, UserRole
from app.middleware.auth import require_auth, admin_required, get_current_user
from app.middleware.tenancy import platform_wide_lookup

users_bp = Blueprint("users", __name__)


@users_bp.route("/", methods=["GET"])
@require_auth
def list_users():
    """
    Listar usuarios
    ---
    tags:
      - Usuarios
    security:
      - BearerAuth: []
    description: >
      Los médicos y asistentes solo ven la lista de médicos activos (para agendar citas).
      Administradores y recepción ven todos los usuarios y pueden filtrar por rol.
    parameters:
      - in: query
        name: role
        type: string
        required: false
        enum: [admin, doctor, receptionist, assistant]
        description: Filtra por rol (solo aplica para admin/recepción)
    responses:
      200:
        description: Lista de usuarios
        schema:
          type: object
          properties:
            users:
              type: array
              items:
                $ref: '#/definitions/User'
            total:
              type: integer
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
    """
    user = get_current_user()
    # Doctors and assistants can only see other doctors (for appointment scheduling)
    if user.role in [UserRole.DOCTOR, UserRole.ASSISTANT]:
        users = User.query.filter_by(role=UserRole.DOCTOR, is_active=True).all()
    else:
        role_filter = request.args.get("role")
        query = User.query
        if role_filter:
            query = query.filter_by(role=role_filter)
        users = query.order_by(User.first_name).all()

    return jsonify({"users": [u.to_dict() for u in users], "total": len(users)}), 200


@users_bp.route("/<int:user_id>", methods=["GET"])
@require_auth
def get_user(user_id):
    """
    Obtener usuario por ID
    ---
    tags:
      - Usuarios
    security:
      - BearerAuth: []
    description: Un usuario puede ver su propio perfil; los administradores pueden ver cualquier perfil.
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
    responses:
      200:
        description: Datos del usuario
        schema:
          type: object
          properties:
            user:
              $ref: '#/definitions/User'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Usuario no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    # Users can view their own profile; admins can view all
    if current.id != user_id and current.role != UserRole.ADMIN:
        return jsonify({"error": "Acceso denegado"}), 403

    user = User.query.get_or_404(user_id, description="Usuario no encontrado")
    return jsonify({"user": user.to_dict()}), 200


@users_bp.route("/", methods=["POST"])
@admin_required
def create_user():
    """
    Crear usuario
    ---
    tags:
      - Usuarios
    security:
      - BearerAuth: []
    description: Solo administradores.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [email, password, first_name, last_name, role]
          properties:
            email:
              type: string
              example: dra.quispe@clinica.com
            password:
              type: string
              example: Doctor2025!
              minLength: 8
            first_name:
              type: string
              example: Lucía
            last_name:
              type: string
              example: Quispe
            role:
              type: string
              enum: [admin, doctor, receptionist, assistant]
              example: doctor
            phone:
              type: string
              example: "591-70099887"
            specialty:
              type: string
              example: Odontopediatría
            license_number:
              type: string
              example: OD-2020-118
    responses:
      201:
        description: Usuario creado correctamente
        schema:
          type: object
          properties:
            user:
              $ref: '#/definitions/User'
            message:
              type: string
      400:
        description: Campo requerido faltante, rol inválido o contraseña muy corta
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado (no es administrador)
        schema:
          $ref: '#/definitions/Error'
      409:
        description: El email ya está registrado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    data = request.get_json()
    required = ["email", "password", "first_name", "last_name", "role"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    email = data["email"].strip().lower()
    # Email is unique platform-wide (not per clinic), so this check must see every clinic.
    with platform_wide_lookup():
        existing = User.query.filter_by(email=email).execution_options(skip_clinic_filter=True).first()
    if existing:
        return jsonify({"error": "El email ya está registrado"}), 409

    try:
        role = UserRole(data["role"])
    except ValueError:
        valid = [r.value for r in UserRole]
        return jsonify({"error": f"Rol inválido. Válidos: {valid}"}), 400

    if len(data["password"]) < 8:
        return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400

    user = User(
        clinic_id=current.clinic_id,
        email=email,
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        role=role,
        phone=data.get("phone"),
        specialty=data.get("specialty"),
        license_number=data.get("license_number"),
    )
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()

    return jsonify({"user": user.to_dict(), "message": "Usuario creado correctamente"}), 201


@users_bp.route("/<int:user_id>", methods=["PUT"])
@require_auth
def update_user(user_id):
    """
    Actualizar usuario
    ---
    tags:
      - Usuarios
    security:
      - BearerAuth: []
    description: >
      Un usuario puede editar su propio perfil (nombre, teléfono, especialidad, matrícula).
      Solo los administradores pueden editar otros usuarios, así como cambiar `role` e `is_active`.
    parameters:
      - in: path
        name: user_id
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
            specialty:
              type: string
            license_number:
              type: string
            role:
              type: string
              enum: [admin, doctor, receptionist, assistant]
              description: Solo administradores
            is_active:
              type: boolean
              description: Solo administradores
    responses:
      200:
        description: Usuario actualizado
        schema:
          type: object
          properties:
            user:
              $ref: '#/definitions/User'
            message:
              type: string
      400:
        description: Rol inválido
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Usuario no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    # Only admins can edit other users
    if current.id != user_id and current.role != UserRole.ADMIN:
        return jsonify({"error": "Acceso denegado"}), 403

    user = User.query.get_or_404(user_id, description="Usuario no encontrado")
    data = request.get_json()

    if "first_name" in data:
        user.first_name = data["first_name"].strip()
    if "last_name" in data:
        user.last_name = data["last_name"].strip()
    if "phone" in data:
        user.phone = data["phone"]
    if "specialty" in data:
        user.specialty = data["specialty"]
    if "license_number" in data:
        user.license_number = data["license_number"]

    # Only admins can change role and active status
    if current.role == UserRole.ADMIN:
        if "role" in data:
            try:
                user.role = UserRole(data["role"])
            except ValueError:
                return jsonify({"error": "Rol inválido"}), 400
        if "is_active" in data:
            user.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify({"user": user.to_dict(), "message": "Usuario actualizado"}), 200


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    """
    Desactivar usuario
    ---
    tags:
      - Usuarios
    security:
      - BearerAuth: []
    description: Baja lógica (soft delete). Solo administradores. No se puede desactivar la propia cuenta.
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
    responses:
      200:
        description: Usuario desactivado correctamente
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: No puede eliminar su propio usuario
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Acceso denegado (no es administrador)
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Usuario no encontrado
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    if current.id == user_id:
        return jsonify({"error": "No puede eliminar su propio usuario"}), 400

    user = User.query.get_or_404(user_id)
    # Soft delete
    user.is_active = False
    db.session.commit()
    return jsonify({"message": "Usuario desactivado correctamente"}), 200


@users_bp.route("/doctors", methods=["GET"])
@require_auth
def list_doctors():
    """
    Listar médicos activos
    ---
    tags:
      - Usuarios
    security:
      - BearerAuth: []
    description: Endpoint rápido para listar médicos activos, usado al agendar citas o crear planes de tratamiento.
    responses:
      200:
        description: Lista de médicos activos
        schema:
          type: object
          properties:
            doctors:
              type: array
              items:
                $ref: '#/definitions/User'
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
    """
    doctors = User.query.filter_by(role=UserRole.DOCTOR, is_active=True).order_by(User.first_name).all()
    return jsonify({"doctors": [d.to_dict() for d in doctors]}), 200
