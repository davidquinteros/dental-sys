"""enable RLS on alembic_version (no legitimate reason to expose it via API)

Revision ID: a1c56de89f03
Revises: f2a891cd47e0
Create Date: 2026-07-10 00:00:00.000000

"""
from alembic import op

revision = 'a1c56de89f03'
down_revision = 'f2a891cd47e0'
branch_labels = None
depends_on = None

# alembic_version is Alembic's own bookkeeping table (one row: the current
# revision id). Unlike clinics/subscription_tiers/pages (previous migration),
# the runtime role (dental_app) has no legitimate reason to ever read or
# write it — only the schema-owner role touches it, during `flask db
# upgrade`. So no policy is created at all: RLS's default-deny blocks
# dental_app and anon/authenticated (PostgREST) alike, while the owner role
# keeps writing it exactly as before (owner bypasses RLS by default without
# FORCE — and FORCE must NOT be added here, or `flask db upgrade` itself
# would break, since it writes this table as the owner role).


def upgrade():
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
