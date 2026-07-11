from app import db
from datetime import datetime
from app.utils.serialization import iso_utc
import enum


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"      # Legacy: kept for DB compatibility, no longer generated
    PAID = "paid"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    QR = "qr"
    # Legacy: kept so existing payment rows still load. No longer offered for
    # new payments — see ALLOWED_PAYMENT_METHODS in routes/billing.py.
    CARD = "card"
    TRANSFER = "transfer"
    OTHER = "other"


class PaymentPlanStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DEFAULTED = "defaulted"


class Invoice(db.Model):
    """Invoice linked to an appointment"""
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    invoice_number = db.Column(db.String(20), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Amounts
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    balance = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    status = db.Column(db.Enum(InvoiceStatus), nullable=False, default=InvoiceStatus.PENDING, index=True)
    notes = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("clinic_id", "invoice_number", name="uq_invoice_clinic_number"),)

    # Relationships
    clinic = db.relationship("Clinic")
    patient = db.relationship("Patient", back_populates="invoices")
    appointment = db.relationship("Appointment", back_populates="invoice")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    items = db.relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="invoice", lazy="dynamic")

    def recalculate(self):
        self.subtotal = sum(float(item.total) for item in self.items)
        self.total = max(0, float(self.subtotal) - float(self.discount))
        self.balance = max(0, float(self.total) - float(self.amount_paid))
        # A cancelled invoice stays cancelled — don't let the balance-derived
        # status below flip it back to pending/paid (recalculate() is also
        # called for unrelated edits, e.g. items, on an already-cancelled row).
        if self.status == InvoiceStatus.CANCELLED:
            return
        if float(self.balance) == 0:
            self.status = InvoiceStatus.PAID
        else:
            self.status = InvoiceStatus.PENDING

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "invoice_number": self.invoice_number,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "appointment_id": self.appointment_id,
            "subtotal": float(self.subtotal),
            "discount": float(self.discount),
            "total": float(self.total),
            "amount_paid": float(self.amount_paid),
            "balance": float(self.balance),
            "status": self.status.value,
            "notes": self.notes,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "items": [item.to_dict() for item in self.items],
            "created_at": iso_utc(self.created_at),
        }

    def __repr__(self):
        return f"<Invoice #{self.invoice_number}>"


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)

    invoice = db.relationship("Invoice", back_populates="items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "total": float(self.total),
        }


class Payment(db.Model):
    """Individual payment record"""
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    received_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.Enum(PaymentMethod), nullable=False, default=PaymentMethod.CASH)
    reference = db.Column(db.String(100), nullable=True)   # Transaction/card reference
    notes = db.Column(db.String(255), nullable=True)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoice = db.relationship("Invoice", back_populates="payments")
    received_by = db.relationship("User", foreign_keys=[received_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "amount": float(self.amount),
            "method": self.method.value,
            "reference": self.reference,
            "notes": self.notes,
            "payment_date": iso_utc(self.payment_date),
            "received_by": self.received_by.full_name if self.received_by else None,
        }


class PaymentPlanInstallment(db.Model):
    """One recorded cuota payment against a PaymentPlan. Amounts are variable —
    the patient can pay whatever they want, not necessarily installment_amount."""
    __tablename__ = "payment_plan_installments"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    payment_plan_id = db.Column(db.Integer, db.ForeignKey("payment_plans.id"), nullable=False, index=True)
    received_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    notes = db.Column(db.String(255), nullable=True)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payment_plan = db.relationship("PaymentPlan", back_populates="installment_payments")
    received_by = db.relationship("User", foreign_keys=[received_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "payment_plan_id": self.payment_plan_id,
            "amount": float(self.amount),
            "notes": self.notes,
            "payment_date": iso_utc(self.payment_date),
            "received_by": self.received_by.full_name if self.received_by else None,
        }


class PaymentPlan(db.Model):
    """Payment plan for long treatments (orthodontics, implants, etc.)"""
    __tablename__ = "payment_plans"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    treatment_plan_id = db.Column(db.Integer, db.ForeignKey("treatment_plans.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(255), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    down_payment = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    installments = db.Column(db.Integer, nullable=False, default=1)
    installment_amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid_installments = db.Column(db.Integer, nullable=False, default=0)
    total_paid = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.Enum(PaymentPlanStatus), nullable=False, default=PaymentPlanStatus.ACTIVE)
    start_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    clinic = db.relationship("Clinic")
    patient = db.relationship("Patient")
    treatment_plan = db.relationship("TreatmentPlan", back_populates="payment_plan")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    installment_payments = db.relationship(
        "PaymentPlanInstallment", back_populates="payment_plan",
        cascade="all, delete-orphan", order_by="PaymentPlanInstallment.payment_date.desc()",
    )

    @property
    def balance(self) -> float:
        return max(0, float(self.total_amount) - float(self.total_paid))

    @property
    def progress_percentage(self) -> float:
        if float(self.total_amount) > 0:
            return round((float(self.total_paid) / float(self.total_amount)) * 100, 1)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "treatment_plan_id": self.treatment_plan_id,
            "treatment_plan_name": self.treatment_plan.name if self.treatment_plan else None,
            "name": self.name,
            "total_amount": float(self.total_amount),
            "down_payment": float(self.down_payment),
            "installments": self.installments,
            "installment_amount": float(self.installment_amount),
            "paid_installments": self.paid_installments,
            "total_paid": float(self.total_paid),
            "balance": self.balance,
            "progress_percentage": self.progress_percentage,
            "status": self.status.value,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "notes": self.notes,
            "created_at": iso_utc(self.created_at),
        }

    def __repr__(self):
        return f"<PaymentPlan #{self.id} - {self.name}>"
