"""add treatment_images (clinical photos per appointment / treatment plan)

Revision ID: d4e1f2a3b5c6
Revises: 5c4fe2b33646
Create Date: 2026-07-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e1f2a3b5c6'
down_revision = '5c4fe2b33646'
branch_labels = None
depends_on = None

TABLE = "treatment_images"

# Same fail-closed clinic-isolation policy as every other tenant-scoped table
# (see a3f9c2d81e47_add_row_level_security.py and 22a40bfa3b04). Applied from
# the start here — both enforcement layers (ORM filter in middleware/tenancy.py
# and this RLS policy) must always be added together for a new clinic_id table.
POLICY_EXPR = (
    "coalesce(current_setting('app.bypass_rls', true), 'off') = 'on' "
    "OR clinic_id = current_setting('app.current_clinic_id', true)::int"
)


def upgrade():
    op.create_table(
        TABLE,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('treatment_id', sa.Integer(), nullable=True),
        sa.Column('treatment_plan_id', sa.Integer(), nullable=True),
        sa.Column('uploaded_by_id', sa.Integer(), nullable=True),
        sa.Column('storage_path', sa.String(length=512), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('caption', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id']),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id']),
        sa.ForeignKeyConstraint(['treatment_id'], ['treatments.id']),
        sa.ForeignKeyConstraint(['treatment_plan_id'], ['treatment_plans.id']),
        sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.create_index(batch_op.f(f'ix_{TABLE}_clinic_id'), ['clinic_id'], unique=False)
        batch_op.create_index(batch_op.f(f'ix_{TABLE}_patient_id'), ['patient_id'], unique=False)
        batch_op.create_index(batch_op.f(f'ix_{TABLE}_treatment_id'), ['treatment_id'], unique=False)
        batch_op.create_index(batch_op.f(f'ix_{TABLE}_treatment_plan_id'), ['treatment_plan_id'], unique=False)

    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY clinic_isolation ON {TABLE} "
        f"USING ({POLICY_EXPR}) WITH CHECK ({POLICY_EXPR})"
    )


def downgrade():
    op.execute(f"DROP POLICY IF EXISTS clinic_isolation ON {TABLE}")
    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.drop_index(batch_op.f(f'ix_{TABLE}_treatment_plan_id'))
        batch_op.drop_index(batch_op.f(f'ix_{TABLE}_treatment_id'))
        batch_op.drop_index(batch_op.f(f'ix_{TABLE}_patient_id'))
        batch_op.drop_index(batch_op.f(f'ix_{TABLE}_clinic_id'))
    op.drop_table(TABLE)
