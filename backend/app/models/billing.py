from app import db
from datetime import datetime
from app.utils.serialization import iso_utc
import enum


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"      # amount_paid > 0 but balance > 0 — reinstated 2026-07-12
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
    # The budget this comprobante charges items against (FCLI-17). NULL = a
    # comprobante unrelated to any budget, which is still the common case
    # (a walk-in consultation, a financed budget's plan, etc.).
    budget_id = db.Column(db.Integer, db.ForeignKey("budgets.id"), nullable=True, index=True)
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
    budget = db.relationship("Budget", foreign_keys=[budget_id])
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
        elif float(self.amount_paid) > 0:
            self.status = InvoiceStatus.PARTIAL
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
            "budget_id": self.budget_id,
            "budget_name": self.budget.name if self.budget else None,
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
    # The budget item this line charges (FCLI-17). NULL = ítem adicional: a
    # product or service that came up at the counter and was never part of the
    # budget. Both cases are legal on the same comprobante.
    budget_item_id = db.Column(db.Integer, db.ForeignKey("budget_items.id"), nullable=True)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)

    invoice = db.relationship("Invoice", back_populates="items")
    budget_item = db.relationship("BudgetItem", back_populates="invoice_lines")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "budget_item_id": self.budget_item_id,
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
    """One recorded payment against a PaymentPlan — the down payment, a "pago completo"
    of one or more citas (amount = count * installment_amount), or a "pago parcial" of any
    amount up to the balance. installment_amount stays fixed either way; see
    PaymentPlan.paid_installments/partial_progress_amount for how progress is derived
    from the total_paid ledger rather than counted per payment."""
    __tablename__ = "payment_plan_installments"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    payment_plan_id = db.Column(db.Integer, db.ForeignKey("payment_plans.id"), nullable=False, index=True)
    received_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    notes = db.Column(db.String(255), nullable=True)
    # Snapshot of the plan's cumulative state right after this payment was applied, so a
    # printed receipt (comprobante) always shows the total-paid/balance as they were AT
    # THAT MOMENT, not the plan's live values (which keep changing with later payments).
    # Nullable: rows created before these columns existed are backfilled by the migration
    # from the ordered ledger; a still-null value falls back to live plan values.
    total_paid_after = db.Column(db.Numeric(10, 2), nullable=True)
    balance_after = db.Column(db.Numeric(10, 2), nullable=True)
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
            "total_paid_after": float(self.total_paid_after) if self.total_paid_after is not None else None,
            "balance_after": float(self.balance_after) if self.balance_after is not None else None,
            "payment_date": iso_utc(self.payment_date),
            "received_by": self.received_by.full_name if self.received_by else None,
        }


class PaymentPlan(db.Model):
    """Payment plan for long treatments (orthodontics, implants, etc.).
    installments = fixed count of citas; installment_amount = fixed cost per
    cita. Both are set at creation (and only editable via PUT before any
    payment beyond the down payment is registered — see routes/billing.py's
    update_payment_plan) and never recomputed by registering a payment."""
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
    end_date = db.Column(db.Date, nullable=True)
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

    @property
    def partial_progress_amount(self) -> float:
        """Amount already paid toward the next not-yet-fully-covered cita (0 if none).
        E.g. paid_installments citas are fully covered; this is the leftover credit
        sitting on top of that, still short of installment_amount."""
        if not float(self.installment_amount):
            return 0.0
        progress = float(self.total_paid) - float(self.down_payment) - self.paid_installments * float(self.installment_amount)
        return round(max(0.0, progress), 2)

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
            "partial_progress_amount": self.partial_progress_amount,
            "total_paid": float(self.total_paid),
            "balance": self.balance,
            "progress_percentage": self.progress_percentage,
            "status": self.status.value,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "notes": self.notes,
            "created_at": iso_utc(self.created_at),
        }

    def __repr__(self):
        return f"<PaymentPlan #{self.id} - {self.name}>"


class BudgetStatus(str, enum.Enum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class BudgetItem(db.Model):
    """One proposed treatment line on a Budget (e.g. "2 caries", "1 extracción").
    Purely descriptive — unlike Invoice/InvoiceItem, nothing here forces
    Budget.total_amount to equal the sum of these; see Budget.items_subtotal.

    Its billing state is **derived, never stored** (FCLI-17): it falls out of the
    comprobante each item is on. That's what makes cancelling a comprobante return
    its items to Pendiente for free, with no compensating code to get wrong."""
    __tablename__ = "budget_items"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    budget_id = db.Column(db.Integer, db.ForeignKey("budgets.id"), nullable=False, index=True)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)

    budget = db.relationship("Budget", back_populates="items")
    # Every comprobante line ever pointed at this item, cancelled ones included —
    # active_invoice_line() is what filters them. No cascade: deleting a budget
    # item that has been invoiced must fail loudly (see the FK note in migration
    # e6a2c1f7b483), never silently delete billing history.
    invoice_lines = db.relationship("InvoiceItem", back_populates="budget_item")

    def active_invoice_line(self):
        """The comprobante line that currently holds this item, or None.

        THE single source of truth for both the displayed state and the
        double-charge guard in routes/billing.py — if these two ever disagreed,
        either items would stay "En cobro" forever after a cancellation, or the
        same item could be charged twice.

        A cancelled comprobante releases its items, so it doesn't count. Note the
        test is `!= CANCELLED` and not a whitelist of live statuses: OVERDUE
        exists in InvoiceStatus and nothing sets it today, and if anything ever
        does, an overdue comprobante still holds its items. Ordered by id so the
        answer is deterministic; the guard means there is at most one.
        """
        return next(
            (line for line in sorted(self.invoice_lines, key=lambda l: l.id)
             if line.invoice and line.invoice.status != InvoiceStatus.CANCELLED),
            None,
        )

    @staticmethod
    def _state_of(line) -> str:
        """The one definition of the three states. Everything else routes through
        here (including to_dict) so a display can never disagree with a guard."""
        if line is None:
            return "pending"
        return "paid" if line.invoice.status == InvoiceStatus.PAID else "billing"

    @property
    def billing_state(self) -> str:
        """'pending' (no live comprobante) | 'billing' (on one, unpaid) | 'paid'."""
        return self._state_of(self.active_invoice_line())

    def to_dict(self) -> dict:
        line = self.active_invoice_line()
        return {
            "id": self.id,
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "total": float(self.total),
            # Derived; the invoice_* trio is None while the item is pending.
            "billing_state": self._state_of(line),
            "invoice_id": line.invoice_id if line else None,
            "invoice_number": line.invoice.invoice_number if line else None,
            "invoice_status": line.invoice.status.value if line else None,
        }


class Budget(db.Model):
    """Printable treatment proposal (FCLI-14, decoupled from the payment plan
    in FCLI-16). Not always converted — a budget can stay in draft or get
    rejected. Items are an informational breakdown of what was observed/
    proposed; total_amount is always the items subtotal (the form derives it
    and renders the field read-only).

    Financing is opt-in via `use_payment_plan`. When it is False the whole
    cita ladder — num_citas/cost_per_cita/down_payment/start_date/end_date —
    is NULL, and the routes force it to NULL regardless of what the client
    sends: NULL is what says "this budget has no schedule", 0 would be a lie.
    When True those fields work exactly as before (see create_budget's
    calc_mode).

    doctor_id/treatment_type/tooth_number are the clinical proposal, and they
    are what accept_budget copies into the auto-created TreatmentPlan —
    treatment_type defaults to 'general' ("Atención General"). treatment_plan_id
    stays nullable: a budget is normally written before any TreatmentPlan
    exists, and accepting is what creates one."""
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    treatment_plan_id = db.Column(db.Integer, db.ForeignKey("treatment_plans.id"), nullable=True, index=True)
    # Nullable in the DB only for budgets that predate FCLI-16; every route
    # that writes a budget requires it, and accept_budget 400s without one.
    doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(255), nullable=False)
    treatment_type = db.Column(db.String(100), nullable=False, default="general",
                               server_default="general")
    tooth_number = db.Column(db.String(20), nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    use_payment_plan = db.Column(db.Boolean, nullable=False, default=False,
                                 server_default=db.false())
    # No python-side default on the three below, deliberately: SQLAlchemy omits
    # a None-valued column from the INSERT, which would let a `default=0`/`=1`
    # fire and turn the "no schedule" NULL into a 0/1 ladder.
    down_payment = db.Column(db.Numeric(10, 2), nullable=True)
    num_citas = db.Column(db.Integer, nullable=True)
    cost_per_cita = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.Enum(BudgetStatus), nullable=False, default=BudgetStatus.DRAFT)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    converted_plan_id = db.Column(db.Integer, db.ForeignKey("payment_plans.id"), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clinic = db.relationship("Clinic")
    patient = db.relationship("Patient")
    treatment_plan = db.relationship("TreatmentPlan")
    converted_plan = db.relationship("PaymentPlan", foreign_keys=[converted_plan_id])
    doctor = db.relationship("User", foreign_keys=[doctor_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    items = db.relationship("BudgetItem", back_populates="budget", cascade="all, delete-orphan")

    @property
    def items_subtotal(self) -> float:
        return round(sum(float(item.total) for item in self.items), 2)

    # ── Billing board (FCLI-17) ─────────────────────────────────────────────
    # These are **item value at budget price**, NOT money received: a comprobante
    # carries a global discount and can be partially paid, so attributing cash to
    # one line is impossible to do honestly. Hence the UI label "En ítems
    # pagados", never "Cobrado". The money still lives in the comprobantes, and
    # GET /billing/summary is untouched and remains the source of truth for cash.
    # Invariant: amount_paid + amount_billed + amount_pending == items_subtotal.

    def _amount_in_state(self, state: str) -> float:
        return round(sum(float(i.total) for i in self.items if i.billing_state == state), 2)

    @property
    def amount_paid(self) -> float:
        """Value of the items sitting on a fully-paid comprobante."""
        return self._amount_in_state("paid")

    @property
    def amount_billed(self) -> float:
        """Value of the items on a live but unpaid comprobante ("En cobro")."""
        return self._amount_in_state("billing")

    @property
    def amount_pending(self) -> float:
        """Value of the items nobody has charged yet."""
        return self._amount_in_state("pending")

    @property
    def is_completed(self) -> bool:
        """Derived label, NOT a BudgetStatus — the enum stays draft/accepted/
        rejected and no migration is needed. A budget with no items is never
        "completed"; it has nothing to charge."""
        return bool(self.items) and self.amount_pending == 0 and self.amount_billed == 0

    @property
    def has_billing(self) -> bool:
        """True once any item is on a live comprobante — the point of no return
        for financing it instead (see link_budget_plan's guard)."""
        return any(i.billing_state != "pending" for i in self.items)

    def to_dict(self, include_items: bool = True) -> dict:
        """include_items=False for list endpoints: the aggregates + items_count
        are all a card needs, and serializing every item of every budget (each
        of which resolves its own comprobante) is what makes list_budgets N+1."""
        data = {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "treatment_plan_id": self.treatment_plan_id,
            "treatment_plan_name": self.treatment_plan.name if self.treatment_plan else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.full_name if self.doctor else None,
            "name": self.name,
            "treatment_type": self.treatment_type,
            "tooth_number": self.tooth_number,
            "total_amount": float(self.total_amount),
            "use_payment_plan": self.use_payment_plan,
            # None (not 0) for an unfinanced budget — the frontend renders the
            # whole cuotas block only when use_payment_plan is true.
            "down_payment": float(self.down_payment) if self.down_payment is not None else None,
            "num_citas": self.num_citas,
            "cost_per_cita": float(self.cost_per_cita) if self.cost_per_cita is not None else None,
            "items_count": len(self.items),
            "items_subtotal": self.items_subtotal,
            "amount_paid": self.amount_paid,
            "amount_billed": self.amount_billed,
            "amount_pending": self.amount_pending,
            "is_completed": self.is_completed,
            "has_billing": self.has_billing,
            "status": self.status.value,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "notes": self.notes,
            "converted_plan_id": self.converted_plan_id,
            "created_at": iso_utc(self.created_at),
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data

    def __repr__(self):
        return f"<Budget #{self.id} - {self.name}>"
