from app import db
from datetime import datetime

BUILTIN_TYPES = [
    {'key': 'consultation', 'label': 'Consulta General',          'color': '#4299e1', 'sort_order': 10},
    {'key': 'cleaning',     'label': 'Limpieza Dental',           'color': '#319795', 'sort_order': 20},
    {'key': 'extraction',   'label': 'Extracción',                'color': '#e53e3e', 'sort_order': 30},
    {'key': 'filling',      'label': 'Empaste / Obturación',      'color': '#dd6b20', 'sort_order': 40},
    {'key': 'endodontics',  'label': 'Endodoncia',                'color': '#805ad5', 'sort_order': 50},
    {'key': 'orthodontics', 'label': 'Ortodoncia',                'color': '#38a169', 'sort_order': 60},
    {'key': 'implant',      'label': 'Implante',                  'color': '#2b6cb0', 'sort_order': 70},
    {'key': 'whitening',    'label': 'Blanqueamiento',            'color': '#d69e2e', 'sort_order': 80},
    {'key': 'crown',        'label': 'Corona',                    'color': '#b7791f', 'sort_order': 90},
    {'key': 'followup',     'label': 'Seguimiento de Tratamiento','color': '#718096', 'sort_order': 100},
    {'key': 'other',        'label': 'Otro',                      'color': '#a0aec0', 'sort_order': 110},
]


class AppointmentTypeCatalog(db.Model):
    __tablename__ = "appointment_types"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    label = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), nullable=True, default='#4299e1')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'key': self.key,
            'label': self.label,
            'color': self.color,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
        }
