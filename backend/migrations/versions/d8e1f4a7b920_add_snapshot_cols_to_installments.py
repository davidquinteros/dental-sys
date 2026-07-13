"""add total_paid_after/balance_after snapshot cols to payment_plan_installments

Freezes each payment's cumulative plan state (total paid + outstanding balance as of
that payment) so a printed receipt shows the numbers AT THE MOMENT of the payment,
not the plan's live values. Backfills existing rows by replaying the ordered ledger.

Revision ID: d8e1f4a7b920
Revises: 3d0a591ca545
Create Date: 2026-07-12 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8e1f4a7b920'
down_revision = '3d0a591ca545'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('payment_plan_installments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_paid_after', sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column('balance_after', sa.Numeric(10, 2), nullable=True))

    # Backfill: for each plan, replay its installments oldest-first and record the
    # running cumulative total. Any gap between the plan's current total_paid and the
    # sum of logged rows (pre-history payments on old plans) is treated as a baseline
    # collected before the first logged row.
    bind = op.get_bind()
    plans = bind.execute(sa.text(
        "SELECT id, total_amount, total_paid FROM payment_plans"
    )).fetchall()

    for plan in plans:
        plan_id = plan[0]
        total_amount = float(plan[1] or 0)
        total_paid = float(plan[2] or 0)

        rows = bind.execute(sa.text(
            "SELECT id, amount FROM payment_plan_installments "
            "WHERE payment_plan_id = :pid ORDER BY payment_date ASC, id ASC"
        ), {"pid": plan_id}).fetchall()

        sum_logged = sum(float(r[1] or 0) for r in rows)
        running = max(0.0, round(total_paid - sum_logged, 2))  # pre-history baseline

        for r in rows:
            running = round(running + float(r[1] or 0), 2)
            balance_after = round(max(0.0, total_amount - running), 2)
            bind.execute(sa.text(
                "UPDATE payment_plan_installments "
                "SET total_paid_after = :tp, balance_after = :bal WHERE id = :id"
            ), {"tp": running, "bal": balance_after, "id": r[0]})


def downgrade():
    with op.batch_alter_table('payment_plan_installments', schema=None) as batch_op:
        batch_op.drop_column('balance_after')
        batch_op.drop_column('total_paid_after')
