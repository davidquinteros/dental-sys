from app import db
from app.models.subscription import SubscriptionStatus
from datetime import datetime


class Clinic(db.Model):
    """A tenant of the SaaS — one dental clinic and all its staff/data."""
    __tablename__ = "clinics"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # SaaS subscription tracking (platform-admin managed, manual billing — no payment gateway).
    subscription_tier_id = db.Column(db.Integer, db.ForeignKey("subscription_tiers.id"), nullable=True)
    subscription_status = db.Column(
        db.Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.TRIAL,
    )
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    next_payment_due_at = db.Column(db.DateTime, nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    subscription_tier = db.relationship("SubscriptionTier")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "is_active": self.is_active,
            "subscription_tier_id": self.subscription_tier_id,
            "subscription_tier_name": self.subscription_tier.name if self.subscription_tier else None,
            "subscription_status": self.subscription_status.value,
            "trial_ends_at": self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            "next_payment_due_at": self.next_payment_due_at.isoformat() if self.next_payment_due_at else None,
            "suspended_at": self.suspended_at.isoformat() if self.suspended_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Clinic {self.name}>"
