from app import db
from datetime import datetime
import enum


class TreatmentPlanStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class Treatment(db.Model):
    """Clinical record for a single appointment/session"""
    __tablename__ = "treatments"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=True)
    treatment_plan_id = db.Column(db.Integer, db.ForeignKey("treatment_plans.id"), nullable=True)

    # Clinical data
    diagnosis = db.Column(db.Text, nullable=True)
    procedure = db.Column(db.String(255), nullable=False)
    tooth_number = db.Column(db.String(20), nullable=True)   # Tooth number/notation (FDI or Universal)
    tooth_surface = db.Column(db.String(20), nullable=True)  # M, D, O, V, L surfaces
    description = db.Column(db.Text, nullable=True)
    clinical_notes = db.Column(db.Text, nullable=True)
    prescriptions = db.Column(db.Text, nullable=True)
    next_steps = db.Column(db.Text, nullable=True)

    # Images / Attachments (stored as JSON array of file paths)
    attachments = db.Column(db.JSON, nullable=True)

    # Timestamps
    performed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    clinic = db.relationship("Clinic")
    patient = db.relationship("Patient", back_populates="treatments")
    doctor = db.relationship("User", foreign_keys=[doctor_id])
    appointment = db.relationship("Appointment", back_populates="treatment")
    treatment_plan = db.relationship("TreatmentPlan", back_populates="sessions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.full_name if self.doctor else None,
            "appointment_id": self.appointment_id,
            "treatment_plan_id": self.treatment_plan_id,
            "treatment_plan_name": self.treatment_plan.name if self.treatment_plan else None,
            "diagnosis": self.diagnosis,
            "procedure": self.procedure,
            "tooth_number": self.tooth_number,
            "tooth_surface": self.tooth_surface,
            "description": self.description,
            "clinical_notes": self.clinical_notes,
            "prescriptions": self.prescriptions,
            "next_steps": self.next_steps,
            "attachments": self.attachments,
            "performed_at": self.performed_at.isoformat() if self.performed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Treatment #{self.id} - {self.procedure}>"


class TreatmentPlan(db.Model):
    """Multi-session treatment plan (endodontics, orthodontics, implants, etc.)"""
    __tablename__ = "treatment_plans"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(255), nullable=False)               # e.g., "Endodoncia #24", "Ortodoncia completa"
    description = db.Column(db.Text, nullable=True)
    treatment_type = db.Column(db.String(100), nullable=False)     # endodontics, orthodontics, implant, etc.
    status = db.Column(db.Enum(TreatmentPlanStatus), default=TreatmentPlanStatus.ACTIVE, nullable=False, index=True)
    total_sessions = db.Column(db.Integer, nullable=True)          # Planned number of sessions
    completed_sessions = db.Column(db.Integer, default=0)

    # Tooth reference
    tooth_number = db.Column(db.String(20), nullable=True)

    # Dates
    start_date = db.Column(db.Date, nullable=True)
    estimated_end_date = db.Column(db.Date, nullable=True)
    actual_end_date = db.Column(db.Date, nullable=True)

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    clinic = db.relationship("Clinic")
    patient = db.relationship("Patient", back_populates="treatment_plans")
    doctor = db.relationship("User", foreign_keys=[doctor_id])
    sessions = db.relationship("Treatment", back_populates="treatment_plan", lazy="dynamic")
    appointments = db.relationship("Appointment", back_populates="treatment_plan", lazy="dynamic")
    payment_plan = db.relationship("PaymentPlan", back_populates="treatment_plan", uselist=False)

    @property
    def progress_percentage(self) -> float:
        if self.total_sessions and self.total_sessions > 0:
            return round((self.completed_sessions / self.total_sessions) * 100, 1)
        return 0.0

    def to_dict(self, include_sessions=False) -> dict:
        data = {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.full_name if self.doctor else None,
            "name": self.name,
            "description": self.description,
            "treatment_type": self.treatment_type,
            "status": self.status.value,
            "total_sessions": self.total_sessions,
            "completed_sessions": self.completed_sessions,
            "progress_percentage": self.progress_percentage,
            "tooth_number": self.tooth_number,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "estimated_end_date": self.estimated_end_date.isoformat() if self.estimated_end_date else None,
            "actual_end_date": self.actual_end_date.isoformat() if self.actual_end_date else None,
            "notes": self.notes,
            "has_payment_plan": self.payment_plan is not None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_sessions:
            data["sessions"] = [s.to_dict() for s in self.sessions.order_by("performed_at")]
        return data

    def __repr__(self):
        return f"<TreatmentPlan #{self.id} - {self.name}>"
