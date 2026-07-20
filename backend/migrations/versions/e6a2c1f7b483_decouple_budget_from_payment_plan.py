"""decouple budget from payment plan (FCLI-16)

Frees the presupuesto from always ending in a plan de pago:

  * `budgets` gains the clinical proposal fields that feed the auto-created
    TreatmentPlan on accept (doctor_id / treatment_type / tooth_number) plus
    `use_payment_plan`, the opt-in financing flag.
  * `num_citas` / `cost_per_cita` / `down_payment` go NOT NULL -> nullable:
    an unfinanced budget has no cita ladder at all, and NULL (not 0) is what
    says so. `total_amount` deliberately stays NOT NULL — the form always
    derives it from the items subtotal.
  * `invoice_items.budget_item_id` / `invoices.budget_id` are FCLI-17's
    columns, added here ON PURPOSE: this is one migration and running a
    second one by hand against prod/testing is worse than shipping two
    nullable columns nothing reads yet.

RLS: NOT touched, deliberately. All four tables (budgets, budget_items,
invoices, invoice_items) already carry their `clinic_isolation` policy from
3d0a591ca545 / a3f9c2d81e47 / c3d67ef01a24. A policy is table-level and is
not affected by adding columns, so there is no missing policy here to
"fix" — resist the urge to add one.

FK caveat for whoever wires up FCLI-17: `update_budget` does
`budget.items.clear()`, which DELETEs BudgetItem rows. Once an invoice line
references one via budget_item_id that DELETE raises an FK violation. It is
unreachable today (PUT is draft-only and billing requires accepted) and it
must NOT be "solved" with ON DELETE CASCADE — that would silently delete
billing history.

Deployment: every change is additive or relaxes a NOT NULL, and SQLAlchemy
always emits explicit column lists (never SELECT *), so the currently
deployed code is blind to all of it. Apply this BEFORE deploying the code.

Revision ID: e6a2c1f7b483
Revises: d8e1f4a7b920
Create Date: 2026-07-16 23:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6a2c1f7b483'
down_revision = 'd8e1f4a7b920'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('budgets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('doctor_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('treatment_type', sa.String(length=100),
                                      nullable=False, server_default='general'))
        batch_op.add_column(sa.Column('tooth_number', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('use_payment_plan', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))
        batch_op.create_foreign_key('fk_budgets_doctor_id_users', 'users', ['doctor_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_budgets_doctor_id'), ['doctor_id'], unique=False)
        # An unfinanced budget has no cita ladder: NULL, not 0.
        batch_op.alter_column('num_citas', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('cost_per_cita', existing_type=sa.Numeric(10, 2), nullable=True)
        batch_op.alter_column('down_payment', existing_type=sa.Numeric(10, 2), nullable=True)

    # FCLI-17's columns, added early on purpose (see module docstring).
    with op.batch_alter_table('invoice_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('budget_item_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_invoice_items_budget_item_id_budget_items', 'budget_items', ['budget_item_id'], ['id']
        )

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('budget_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_invoices_budget_id_budgets', 'budgets', ['budget_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_invoices_budget_id'), ['budget_id'], unique=False)

    # ── Backfill ────────────────────────────────────────────────────────────
    # Every budget that exists today was created by the old form, where
    # financing was mandatory — so they are all use_payment_plan = true.
    # server_default=false above already stamped them false; flip them back.
    op.execute("UPDATE budgets SET use_payment_plan = true")

    # Copy the clinical fields from the linked treatment_plan where there is
    # one, so an old Ortodoncia budget doesn't read as "Atención General" and
    # doesn't lose its doctor. Budgets with no linked plan keep the 'general'
    # default and a NULL doctor_id (the accept route asks for one).
    op.execute(
        """
        UPDATE budgets b
        SET treatment_type = tp.treatment_type,
            doctor_id      = tp.doctor_id
        FROM treatment_plans tp
        WHERE b.treatment_plan_id = tp.id
        """
    )


def downgrade():
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_invoices_budget_id'))
        batch_op.drop_constraint('fk_invoices_budget_id_budgets', type_='foreignkey')
        batch_op.drop_column('budget_id')

    with op.batch_alter_table('invoice_items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_invoice_items_budget_item_id_budget_items', type_='foreignkey')
        batch_op.drop_column('budget_item_id')

    # Re-tightening the NOT NULLs needs the unfinanced budgets to carry a
    # value again — restore the pre-FCLI-16 shape (a 1-cita ladder priced at
    # the full total) rather than failing the downgrade outright.
    op.execute("UPDATE budgets SET num_citas = 1 WHERE num_citas IS NULL")
    op.execute("UPDATE budgets SET down_payment = 0 WHERE down_payment IS NULL")
    op.execute("UPDATE budgets SET cost_per_cita = total_amount - COALESCE(down_payment, 0) "
               "WHERE cost_per_cita IS NULL")

    with op.batch_alter_table('budgets', schema=None) as batch_op:
        batch_op.alter_column('down_payment', existing_type=sa.Numeric(10, 2), nullable=False)
        batch_op.alter_column('cost_per_cita', existing_type=sa.Numeric(10, 2), nullable=False)
        batch_op.alter_column('num_citas', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index(batch_op.f('ix_budgets_doctor_id'))
        batch_op.drop_constraint('fk_budgets_doctor_id_users', type_='foreignkey')
        batch_op.drop_column('use_payment_plan')
        batch_op.drop_column('tooth_number')
        batch_op.drop_column('treatment_type')
        batch_op.drop_column('doctor_id')
