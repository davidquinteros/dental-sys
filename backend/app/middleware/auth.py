from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models.user import User, UserRole


def get_current_user() -> User | None:
    """Get current authenticated user from JWT"""
    user_id = get_jwt_identity()
    if user_id:
        return User.query.get(user_id)
    return None


def require_auth(f):
    """Require valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        verify_jwt_in_request()
        user = get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "Usuario no autorizado o inactivo"}), 403
        return f(*args, **kwargs)
    return decorated


def require_roles(*roles: UserRole):
    """Require specific roles to access a route"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            verify_jwt_in_request()
            user = get_current_user()
            if not user or not user.is_active:
                return jsonify({"error": "Usuario no autorizado"}), 403
            if user.role not in roles:
                return jsonify({
                    "error": "Acceso denegado",
                    "message": f"Se requiere uno de los roles: {[r.value for r in roles]}"
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def admin_required(f):
    """Only admins"""
    return require_roles(UserRole.ADMIN)(f)


def doctor_or_admin_required(f):
    """Doctors and admins"""
    return require_roles(UserRole.ADMIN, UserRole.DOCTOR)(f)


def medical_staff_required(f):
    """All medical staff (doctor, assistant) + admin"""
    return require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.ASSISTANT)(f)


def clinical_access_required(f):
    """All roles that can interact with patients"""
    return require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST, UserRole.ASSISTANT)(f)
