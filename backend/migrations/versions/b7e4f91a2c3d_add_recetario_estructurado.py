"""add structured recetario fields to treatments and clinics

Revision ID: b7e4f91a2c3d
Revises: a994a6c8d690
Create Date: 2026-07-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e4f91a2c3d'
down_revision = 'a994a6c8d690'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('treatments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_prescription', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('medications', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('prescription_notes', sa.Text(), nullable=True))

    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.add_column(sa.Column('address', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('logo_url', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.drop_column('logo_url')
        batch_op.drop_column('phone')
        batch_op.drop_column('address')

    with op.batch_alter_table('treatments', schema=None) as batch_op:
        batch_op.drop_column('prescription_notes')
        batch_op.drop_column('medications')
        batch_op.drop_column('has_prescription')
