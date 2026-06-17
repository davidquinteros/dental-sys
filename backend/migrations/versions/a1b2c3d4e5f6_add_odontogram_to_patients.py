"""add odontogram to patients

Revision ID: a1b2c3d4e5f6
Revises: 724c61a72994
Create Date: 2026-06-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '724c61a72994'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('patients', sa.Column('odontogram', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('patients', 'odontogram')
