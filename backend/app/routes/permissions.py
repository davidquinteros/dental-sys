from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app import db
from app.models.user import User, UserRole
from app.models.permission import Page, RolePermission
from app.middleware.auth import admin_required, require_auth, get_current_user

permissions_bp = Blueprint("permissions", __name__)

ALL_ROLES = [r.value for r in UserRole]


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_current_user() -> User | None:
    try:
        verify_jwt_in_request()
        uid = get_jwt_identity()
        return User.query.get(uid) if uid else None
    except Exception:
        return None


def _build_matrix() -> dict:
    """Return {role: {page_key: {can_view, can_create, can_edit, can_delete}}}"""
    pages = Page.query.order_by(Page.sort_order).all()
    perms = RolePermission.query.all()
    perm_map = {(p.role.value, p.page_key): p for p in perms}

    matrix = {}
    for role in ALL_ROLES:
        matrix[role] = {}
        for page in pages:
            p = perm_map.get((role, page.key))
            matrix[role][page.key] = {
                "can_view": p.can_view if p else False,
                "can_create": p.can_create if p else False,
                "can_edit": p.can_edit if p else False,
                "can_delete": p.can_delete if p else False,
            }
    return matrix


# ─── Pages CRUD (admin only) ──────────────────────────────────────────────────

@permissions_bp.route("/pages", methods=["GET"])
@require_auth
def list_pages():
    """
    Listar todas las páginas registradas
    ---
    tags: [Permisos]
    security: [Bearer: []]
    responses:
      200:
        description: Lista de páginas
    """
    pages = Page.query.order_by(Page.sort_order).all()
    return jsonify({"pages": [p.to_dict() for p in pages]}), 200


@permissions_bp.route("/pages", methods=["POST"])
@admin_required
def create_page():
    """
    Crear una nueva página
    ---
    tags: [Permisos]
    security: [Bearer: []]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [key, label, route]
          properties:
            key: {type: string}
            label: {type: string}
            route: {type: string}
            icon: {type: string}
            description: {type: string}
            sort_order: {type: integer}
    responses:
      201:
        description: Página creada
      400:
        description: Datos inválidos o clave duplicada
    """
    current = get_current_user()
    data = request.get_json() or {}
    key = (data.get("key") or "").strip().lower().replace(" ", "_")
    label = (data.get("label") or "").strip()
    route = (data.get("route") or "").strip()

    if not key or not label or not route:
        return jsonify({"error": "key, label y route son requeridos"}), 400
    if Page.query.filter_by(key=key).first():
        return jsonify({"error": f"Ya existe una página con clave '{key}'"}), 400

    page = Page(
        key=key,
        label=label,
        route=route,
        icon=data.get("icon"),
        description=data.get("description"),
        is_system=False,
        sort_order=data.get("sort_order", 99),
    )
    db.session.add(page)

    # Create default denied-permissions for all roles, scoped to this clinic
    for role in UserRole:
        rp = RolePermission(clinic_id=current.clinic_id, role=role, page_key=key)
        db.session.add(rp)

    db.session.commit()
    return jsonify({"page": page.to_dict()}), 201


@permissions_bp.route("/pages/<int:page_id>", methods=["PUT"])
@admin_required
def update_page(page_id: int):
    """
    Actualizar una página existente
    ---
    tags: [Permisos]
    security: [Bearer: []]
    parameters:
      - in: path
        name: page_id
        type: integer
        required: true
    responses:
      200:
        description: Página actualizada
      404:
        description: Página no encontrada
    """
    page = db.session.get(Page, page_id)
    if not page:
        return jsonify({"error": "Página no encontrada"}), 404

    data = request.get_json() or {}
    if "label" in data:
        page.label = data["label"].strip()
    if "route" in data:
        page.route = data["route"].strip()
    if "icon" in data:
        page.icon = data["icon"]
    if "description" in data:
        page.description = data["description"]
    if "sort_order" in data:
        page.sort_order = int(data["sort_order"])

    db.session.commit()
    return jsonify({"page": page.to_dict()}), 200


@permissions_bp.route("/pages/<int:page_id>", methods=["DELETE"])
@admin_required
def delete_page(page_id: int):
    """
    Eliminar una página (solo páginas no-sistema)
    ---
    tags: [Permisos]
    security: [Bearer: []]
    parameters:
      - in: path
        name: page_id
        type: integer
        required: true
    responses:
      200:
        description: Página eliminada
      403:
        description: No se pueden eliminar páginas del sistema
      404:
        description: Página no encontrada
    """
    page = db.session.get(Page, page_id)
    if not page:
        return jsonify({"error": "Página no encontrada"}), 404
    if page.is_system:
        return jsonify({"error": "No se pueden eliminar páginas del sistema"}), 403

    db.session.delete(page)
    db.session.commit()
    return jsonify({"message": "Página eliminada"}), 200


# ─── Permission matrix (admin only) ──────────────────────────────────────────

@permissions_bp.route("/matrix", methods=["GET"])
@admin_required
def get_matrix():
    """
    Obtener la matriz completa de permisos (roles × páginas)
    ---
    tags: [Permisos]
    security: [Bearer: []]
    responses:
      200:
        description: Matriz de permisos
    """
    pages = Page.query.order_by(Page.sort_order).all()
    return jsonify({
        "pages": [p.to_dict() for p in pages],
        "roles": ALL_ROLES,
        "matrix": _build_matrix(),
    }), 200


@permissions_bp.route("/matrix", methods=["PUT"])
@admin_required
def save_matrix():
    """
    Guardar la matriz de permisos completa
    ---
    tags: [Permisos]
    security: [Bearer: []]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          description: >
            Mapa {role: {page_key: {can_view, can_create, can_edit, can_delete}}}
    responses:
      200:
        description: Permisos guardados
    """
    current = get_current_user()
    data = request.get_json() or {}
    # data = { role: { page_key: { can_view, can_create, can_edit, can_delete } } }
    valid_roles = {r.value: r for r in UserRole}
    valid_pages = {p.key for p in Page.query.all()}

    for role_str, pages_map in data.items():
        if role_str not in valid_roles:
            continue
        role_enum = valid_roles[role_str]
        for page_key, flags in pages_map.items():
            if page_key not in valid_pages:
                continue
            rp = RolePermission.query.filter_by(
                role=role_enum, page_key=page_key
            ).first()
            if not rp:
                rp = RolePermission(clinic_id=current.clinic_id, role=role_enum, page_key=page_key)
                db.session.add(rp)
            rp.can_view = bool(flags.get("can_view", False))
            rp.can_create = bool(flags.get("can_create", False))
            rp.can_edit = bool(flags.get("can_edit", False))
            rp.can_delete = bool(flags.get("can_delete", False))

    db.session.commit()
    return jsonify({"message": "Permisos guardados", "matrix": _build_matrix()}), 200


# ─── Current user's permissions (all authenticated users) ────────────────────

@permissions_bp.route("/me", methods=["GET"])
@require_auth
def my_permissions():
    """
    Obtener las páginas accesibles para el rol del usuario actual
    ---
    tags: [Permisos]
    security: [Bearer: []]
    responses:
      200:
        description: Lista de page_keys con acceso can_view
    """
    user = _get_current_user()
    if not user:
        return jsonify({"error": "No autorizado"}), 401

    perms = RolePermission.query.filter_by(role=user.role, can_view=True).all()
    viewable = [p.page_key for p in perms]

    # Admins always see everything
    if user.role == UserRole.ADMIN:
        all_keys = [p.key for p in Page.query.order_by(Page.sort_order).all()]
        viewable = all_keys

    pages = Page.query.order_by(Page.sort_order).all()
    page_map = {p.key: p.to_dict() for p in pages}

    return jsonify({
        "role": user.role.value,
        "viewable_pages": viewable,
        "pages": [page_map[k] for k in viewable if k in page_map],
    }), 200
