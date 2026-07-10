"""add email column to clinics

Revision ID: c8f5a2e91b4d
Revises: b7e4f91a2c3d
Create Date: 2026-07-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8f5a2e91b4d'
down_revision = 'b7e4f91a2c3d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.drop_column('email')
