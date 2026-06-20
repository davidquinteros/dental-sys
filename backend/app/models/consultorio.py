from app import db
from datetime import datetime


class Consultorio(db.Model):
    __tablename__ = "consultorios"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    color = db.Column(db.String(7), nullable=True, default="#4299e1")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    clinic = db.relationship("Clinic")
    appointments = db.relationship("Appointment", back_populates="consultorio")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "name": self.name,
            "description": self.description,
            "color": self.color or "#4299e1",
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<Consultorio {self.name}>"
