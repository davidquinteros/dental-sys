"""add payment_plan_installments (per-payment history for variable cuota amounts)

Revision ID: 22a40bfa3b04
Revises: 4a743dc44e09
Create Date: 2026-06-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '22a40bfa3b04'
down_revision = '4a743dc44e09'
branch_labels = None
depends_on = None

TABLE = "payment_plan_installments"

# Same fail-closed policy as the rest of the clinic-scoped tables (see
# a3f9c2d81e47_add_row_level_security.py) — applied here from the start,
# unlike subscription_payments which shipped without it and had to be
# patched in afterward (f3f85dc00800).
POLICY_EXPR = (
    "coalesce(current_setting('app.bypass_rls', true), 'off') = 'on' "
    "OR clinic_id = current_setting('app.current_clinic_id', true)::int"
)


def upgrade():
    op.create_table(
        TABLE,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False),
        sa.Column('payment_plan_id', sa.Integer(), nullable=False),
        sa.Column('received_by_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.Column('payment_date', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id']),
        sa.ForeignKeyConstraint(['payment_plan_id'], ['payment_plans.id']),
        sa.ForeignKeyConstraint(['received_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.create_index(batch_op.f(f'ix_{TABLE}_clinic_id'), ['clinic_id'], unique=False)
        batch_op.create_index(batch_op.f(f'ix_{TABLE}_payment_plan_id'), ['payment_plan_id'], unique=False)

    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY clinic_isolation ON {TABLE} "
        f"USING ({POLICY_EXPR}) WITH CHECK ({POLICY_EXPR})"
    )


def downgrade():
    op.execute(f"DROP POLICY IF EXISTS clinic_isolation ON {TABLE}")
    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.drop_index(batch_op.f(f'ix_{TABLE}_payment_plan_id'))
        batch_op.drop_index(batch_op.f(f'ix_{TABLE}_clinic_id'))
    op.drop_table(TABLE)
