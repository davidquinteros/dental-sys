from app import db
from app.models.subscription import SubscriptionStatus
from datetime import datetime


class Clinic(db.Model):
    """A tenant of the SaaS — one dental clinic and all its staff/data."""
    __tablename__ = "clinics"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default=db.true())
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Printable-header info (FCLI-11) — shown on the recetario print view.
    address = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    logo_url = db.Column(db.String(500), nullable=True)
    email = db.Column(db.String(255), nullable=True)  # Email de contacto (encabezado del recetario)

    # SaaS subscription tracking (platform-admin managed, manual billing — no payment gateway).
    subscription_tier_id = db.Column(db.Integer, db.ForeignKey("subscription_tiers.id"), nullable=True)
    subscription_status = db.Column(
        db.Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.TRIAL,
        server_default="TRIAL",
    )
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    next_payment_due_at = db.Column(db.DateTime, nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # When the clinic's *current* plan (trial or paid) started/expires.
    # plan_expires_at is the authoritative date access_blocked() checks for
    # any status, not just trial — editable by the platform admin to
    # extend/shorten access regardless of which plan is assigned.
    plan_started_at = db.Column(db.DateTime, nullable=True)
    plan_expires_at = db.Column(db.DateTime, nullable=True)

    subscription_tier = db.relationship("SubscriptionTier")

    def access_blocked(self) -> bool:
        """True if this clinic's staff should be locked out of the app —
        manually deactivated/suspended/cancelled by the platform admin, or
        an expired trial that was never converted to a paid plan. PAST_DUE
        is deliberately not blocking: it's a grace-period warning state."""
        if not self.is_active:
            return True
        if self.subscription_status in (SubscriptionStatus.SUSPENDED, SubscriptionStatus.CANCELLED):
            return True
        if self.plan_expires_at and datetime.utcnow() > self.plan_expires_at:
            return True
        if self.subscription_status == SubscriptionStatus.TRIAL and self.trial_ends_at:
            return datetime.utcnow() > self.trial_ends_at
        return False

    def access_blocked_message(self) -> str:
        if not self.is_active:
            return "Su clínica fue desactivada por el administrador de la plataforma."
        if self.subscription_status == SubscriptionStatus.SUSPENDED:
            return "Su clínica fue suspendida. Contacte al administrador de la plataforma."
        if self.subscription_status == SubscriptionStatus.CANCELLED:
            return "La suscripción de su clínica fue cancelada. Contacte al administrador de la plataforma."
        if self.subscription_status == SubscriptionStatus.TRIAL:
            return "Su período de prueba de 30 días ha finalizado. Contacte al administrador de la plataforma para activar su plan."
        return "Su plan venció. Contacte al administrador de la plataforma para renovarlo."

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "is_active": self.is_active,
            "address": self.address,
            "phone": self.phone,
            "logo_url": self.logo_url,
            "email": self.email,
            "subscription_tier_id": self.subscription_tier_id,
            "subscription_tier_name": self.subscription_tier.name if self.subscription_tier else None,
            "subscription_status": self.subscription_status.value,
            "trial_ends_at": self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            "next_payment_due_at": self.next_payment_due_at.isoformat() if self.next_payment_due_at else None,
            "suspended_at": self.suspended_at.isoformat() if self.suspended_at else None,
            "plan_started_at": self.plan_started_at.isoformat() if self.plan_started_at else None,
            "plan_expires_at": self.plan_expires_at.isoformat() if self.plan_expires_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Clinic {self.name}>"
