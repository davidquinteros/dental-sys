from app import db
from datetime import datetime
import enum


class BloodType(str, enum.Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"
    UNKNOWN = "unknown"


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    # Personal information
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    document_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    document_type = db.Column(db.String(20), default="CI", nullable=False)  # CI, Passport, etc.
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10), nullable=True)  # M, F, Other

    # Contact
    phone = db.Column(db.String(20), nullable=True)
    phone_emergency = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(80), nullable=True)

    # Medical basic info
    blood_type = db.Column(db.Enum(BloodType), default=BloodType.UNKNOWN)
    allergies = db.Column(db.Text, nullable=True)
    medical_notes = db.Column(db.Text, nullable=True)  # General medical notes

    # Odontogram — JSON map of tooth number → {status, notes}
    odontogram = db.Column(db.JSON, nullable=True, default=dict)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appointments = db.relationship("Appointment", back_populates="patient", lazy="dynamic")
    treatments = db.relationship("Treatment", back_populates="patient", lazy="dynamic")
    treatment_plans = db.relationship("TreatmentPlan", back_populates="patient", lazy="dynamic")
    invoices = db.relationship("Invoice", back_populates="patient", lazy="dynamic")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int | None:
        if self.date_of_birth:
            today = datetime.today().date()
            return (today - self.date_of_birth).days // 365
        return None

    def to_dict(self, include_history=False) -> dict:
        data = {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "document_number": self.document_number,
            "document_type": self.document_type,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "age": self.age,
            "gender": self.gender,
            "phone": self.phone,
            "phone_emergency": self.phone_emergency,
            "email": self.email,
            "address": self.address,
            "city": self.city,
            "blood_type": self.blood_type.value if self.blood_type else None,
            "allergies": self.allergies,
            "medical_notes": self.medical_notes,
            "odontogram": self.odontogram or {},
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_history:
            data["total_appointments"] = self.appointments.count()
            data["total_treatments"] = self.treatments.count()
            data["active_treatment_plans"] = self.treatment_plans.filter_by(status="active").count()
        return data

    def __repr__(self):
        return f"<Patient {self.full_name} ({self.document_number})>"
