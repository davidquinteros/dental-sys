"""add QR value to the paymentmethod enum

Revision ID: 4a743dc44e09
Revises: f3f85dc00800
Create Date: 2026-06-22 09:00:00.000000

"""
from alembic import op

revision = '4a743dc44e09'
down_revision = 'f3f85dc00800'
branch_labels = None
depends_on = None


def upgrade():
    # Postgres 12+ allows ADD VALUE inside a transaction as long as the new
    # value isn't used in the same transaction — fine here, we only add it.
    op.execute("ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'QR'")


def downgrade():
    # Postgres has no DROP VALUE for enums short of recreating the type;
    # leaving 'QR' in place on downgrade is harmless (just an unused label).
    pass
