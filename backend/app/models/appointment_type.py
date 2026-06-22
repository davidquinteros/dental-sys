from app import db
from datetime import datetime

BUILTIN_TYPES = [
    {'key': 'consulta_general', 'label': 'Consulta General', 'color': '#4299e1', 'sort_order': 10},
    {'key': 'limpieza_dental',  'label': 'Limpieza Dental',  'color': '#319795', 'sort_order': 20},
    {'key': 'extraccion',       'label': 'Extracción',       'color': '#e53e3e', 'sort_order': 30},
    {'key': 'blanqueamiento',   'label': 'Blanqueamiento',   'color': '#d69e2e', 'sort_order': 40},
    {'key': 'corona',           'label': 'Corona',           'color': '#b7791f', 'sort_order': 50},
]


class AppointmentTypeCatalog(db.Model):
    __tablename__ = "appointment_types"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    key = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), nullable=True, default='#4299e1')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("clinic_id", "key", name="uq_appttype_clinic_key"),)

    clinic = db.relationship("Clinic")

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'clinic_id': self.clinic_id,
            'key': self.key,
            'label': self.label,
            'color': self.color,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
        }
