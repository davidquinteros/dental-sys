"""add row level security to subscription_payments (closes tenancy gap)

Revision ID: f3f85dc00800
Revises: 1c3fdcef13ba
Create Date: 2026-06-21 10:00:00.000000

"""
from alembic import op

revision = 'f3f85dc00800'
down_revision = '1c3fdcef13ba'
branch_labels = None
depends_on = None

# subscription_payments has a clinic_id (one row per clinic's SaaS payment) and
# was missed when it was introduced — every other clinic_id-bearing table gets
# RLS as defense-in-depth (see a3f9c2d81e47). subscription_tiers is correctly
# excluded: it's a platform-wide price list with no clinic_id.
TABLE = "subscription_payments"

POLICY_EXPR = (
    "coalesce(current_setting('app.bypass_rls', true), 'off') = 'on' "
    "OR clinic_id = current_setting('app.current_clinic_id', true)::int"
)


def upgrade():
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY clinic_isolation ON {TABLE} "
        f"USING ({POLICY_EXPR}) WITH CHECK ({POLICY_EXPR})"
    )


def downgrade():
    op.execute(f"DROP POLICY IF EXISTS clinic_isolation ON {TABLE}")
    op.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY")
