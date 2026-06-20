from app import db
from app.models.user import UserRole
from datetime import datetime


class Page(db.Model):
    """A navigable page/section in the app that can be assigned to roles."""
    __tablename__ = "pages"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)   # e.g. 'patients'
    label = db.Column(db.String(100), nullable=False)              # e.g. 'Pacientes'
    route = db.Column(db.String(100), nullable=False)              # e.g. '/patients'
    icon = db.Column(db.Text, nullable=True)                       # SVG markup
    description = db.Column(db.String(255), nullable=True)
    is_system = db.Column(db.Boolean, default=False, nullable=False)  # system pages can't be deleted
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    permissions = db.relationship("RolePermission", back_populates="page",
                                  cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "label": self.label,
            "route": self.route,
            "icon": self.icon,
            "description": self.description,
            "is_system": self.is_system,
            "sort_order": self.sort_order,
        }

    def __repr__(self):
        return f"<Page {self.key}>"


class RolePermission(db.Model):
    """Maps a role to a page with granular access flags."""
    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    role = db.Column(db.Enum(UserRole), nullable=False)
    page_key = db.Column(db.String(50), db.ForeignKey("pages.key", ondelete="CASCADE"), nullable=False)
    can_view = db.Column(db.Boolean, default=False, nullable=False)
    can_create = db.Column(db.Boolean, default=False, nullable=False)
    can_edit = db.Column(db.Boolean, default=False, nullable=False)
    can_delete = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("clinic_id", "role", "page_key", name="uq_role_page_clinic"),)

    clinic = db.relationship("Clinic")
    page = db.relationship("Page", back_populates="permissions")

    def to_dict(self) -> dict:
        return {
            "clinic_id": self.clinic_id,
            "role": self.role.value,
            "page_key": self.page_key,
            "can_view": self.can_view,
            "can_create": self.can_create,
            "can_edit": self.can_edit,
            "can_delete": self.can_delete,
        }

    def __repr__(self):
        return f"<RolePermission {self.role.value}:{self.page_key}>"
