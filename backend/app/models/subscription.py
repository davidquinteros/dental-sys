from app import db
from datetime import datetime
import enum


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class SubscriptionTier(db.Model):
    """A plan level a clinic can be subscribed to (platform-wide config, not clinic-scoped)."""
    __tablename__ = "subscription_tiers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    monthly_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    max_users = db.Column(db.Integer, nullable=True)  # null = unlimited
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "monthly_price": float(self.monthly_price),
            "max_users": self.max_users,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<SubscriptionTier {self.code}>"


class SubscriptionPayment(db.Model):
    """A manually-recorded SaaS subscription payment from a clinic (not a patient invoice)."""
    __tablename__ = "subscription_payments"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    period_start = db.Column(db.Date, nullable=True)
    period_end = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    clinic = db.relationship("Clinic")
    recorded_by = db.relationship("User", foreign_keys=[recorded_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "amount": float(self.amount),
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "notes": self.notes,
            "recorded_by": self.recorded_by.full_name if self.recorded_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<SubscriptionPayment #{self.id} clinic={self.clinic_id}>"
