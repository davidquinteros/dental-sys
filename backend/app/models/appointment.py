from app import db
from datetime import datetime
import enum


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"      # Programada
    CONFIRMED = "confirmed"      # Confirmada por paciente
    IN_PROGRESS = "in_progress"  # En curso
    COMPLETED = "completed"      # Completada
    CANCELLED = "cancelled"      # Cancelada
    NO_SHOW = "no_show"          # Paciente no se presentó


class AppointmentType(str, enum.Enum):
    CONSULTATION = "consultation"        # Consulta general
    CLEANING = "cleaning"                # Limpieza dental
    EXTRACTION = "extraction"            # Extracción
    FILLING = "filling"                  # Empaste / Obturación
    ENDODONTICS = "endodontics"          # Endodoncia
    ORTHODONTICS = "orthodontics"        # Ortodoncia
    IMPLANT = "implant"                  # Implante
    WHITENING = "whitening"              # Blanqueamiento
    CROWN = "crown"                      # Corona
    FOLLOWUP = "followup"                # Seguimiento de tratamiento
    OTHER = "other"


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Scheduling
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, default=30, nullable=False)
    appointment_type = db.Column(db.String(100), nullable=False, default="consulta_general")
    status = db.Column(db.Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.SCHEDULED, index=True)

    # Consultorio (room) where the appointment takes place
    consultorio_id = db.Column(db.Integer, db.ForeignKey("consultorios.id"), nullable=True, index=True)

    # Treatment plan link (for multi-session treatments)
    treatment_plan_id = db.Column(db.Integer, db.ForeignKey("treatment_plans.id"), nullable=True)
    session_number = db.Column(db.Integer, nullable=True)  # Which session in the plan

    # Notes
    reason = db.Column(db.String(500), nullable=True)        # Reason for visit
    notes = db.Column(db.Text, nullable=True)                # Internal notes
    cancellation_reason = db.Column(db.String(255), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    clinic = db.relationship("Clinic")
    patient = db.relationship("Patient", back_populates="appointments")
    doctor = db.relationship("User", foreign_keys=[doctor_id], back_populates="appointments_as_doctor")
    created_by = db.relationship("User", foreign_keys=[created_by_id], back_populates="appointments_created")
    consultorio = db.relationship("Consultorio", back_populates="appointments")
    treatment_plan = db.relationship("TreatmentPlan", back_populates="appointments")
    treatment = db.relationship("Treatment", back_populates="appointment", uselist=False)
    invoice = db.relationship("Invoice", back_populates="appointment", uselist=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.full_name if self.doctor else None,
            "consultorio_id": self.consultorio_id,
            "consultorio_name": self.consultorio.name if self.consultorio else None,
            "created_by_id": self.created_by_id,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "duration_minutes": self.duration_minutes,
            "appointment_type": self.appointment_type,
            "status": self.status.value,
            "treatment_plan_id": self.treatment_plan_id,
            "treatment_plan_name": self.treatment_plan.name if self.treatment_plan else None,
            "session_number": self.session_number,
            "reason": self.reason,
            "notes": self.notes,
            "cancellation_reason": self.cancellation_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "has_treatment": self.treatment is not None,
            "has_invoice": self.invoice is not None,
        }

    def __repr__(self):
        return f"<Appointment #{self.id} {self.patient_id} @ {self.scheduled_at}>"
