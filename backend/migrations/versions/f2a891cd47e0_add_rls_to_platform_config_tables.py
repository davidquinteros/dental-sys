"""enable RLS on platform-wide config tables (clinics, subscription_tiers, pages)

Revision ID: f2a891cd47e0
Revises: b7d924fa61ec
Create Date: 2026-07-10 00:00:00.000000

"""
from alembic import op

revision = 'f2a891cd47e0'
down_revision = 'b7d924fa61ec'
branch_labels = None
depends_on = None

# These three tables are genuinely platform-wide config with no clinic_id —
# correctly excluded from the clinic_isolation pattern (see
# a3f9c2d81e47_add_row_level_security.py). Supabase's Security Advisor still
# flags "RLS Disabled in Public" because, with RLS off, anything exposed to
# PostgREST (the anon/authenticated roles) can read/write them directly. This
# app never uses Supabase's PostgREST/client-side auth — only the custom
# dental_app (runtime) and owner (migrations) roles ever touch these tables —
# so the fix is a permissive policy scoped `TO dental_app` only: RLS's
# default-deny then blocks anon/authenticated (no matching policy), while
# dental_app keeps unrestricted read/write and the owner role keeps its
# default RLS bypass for migrations/seeding (no FORCE — unlike the
# clinic-scoped tables, there's no per-row isolation to enforce here, just
# access-role gating).
TABLES = ["clinics", "subscription_tiers", "pages"]


def upgrade():
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY app_access ON {table} "
            f"FOR ALL TO dental_app USING (true) WITH CHECK (true)"
        )


def downgrade():
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS app_access ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
