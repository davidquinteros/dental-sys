from app import db, bcrypt
from datetime import datetime
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    ASSISTANT = "assistant"
    GUEST = "guest"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=True, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.RECEPTIONIST)
    phone = db.Column(db.String(20), nullable=True)
    specialty = db.Column(db.String(120), nullable=True)  # For doctors
    license_number = db.Column(db.String(50), nullable=True)  # For doctors
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # Platform staff (us, the SaaS operator) — separate from clinic role, not exposed in the roles UI
    is_platform_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clinic = db.relationship("Clinic")

    # Relationships
    appointments_as_doctor = db.relationship(
        "Appointment", foreign_keys="Appointment.doctor_id", back_populates="doctor", lazy="dynamic"
    )
    appointments_created = db.relationship(
        "Appointment", foreign_keys="Appointment.created_by_id", back_populates="created_by", lazy="dynamic"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def has_role(self, *roles) -> bool:
        return self.role in roles

    def can_manage_users(self) -> bool:
        return self.role == UserRole.ADMIN

    def can_view_all_appointments(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.RECEPTIONIST]

    def can_manage_billing(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.RECEPTIONIST]

    def can_manage_treatments(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.DOCTOR, UserRole.ASSISTANT]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "clinic_name": self.clinic.name if self.clinic else None,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "role": self.role.value,
            "phone": self.phone,
            "specialty": self.specialty,
            "license_number": self.license_number,
            "is_active": self.is_active,
            "is_platform_admin": self.is_platform_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User {self.email} ({self.role.value})>"
