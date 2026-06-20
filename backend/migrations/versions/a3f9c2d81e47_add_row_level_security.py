"""add row level security as defense-in-depth for multi-tenancy

Revision ID: a3f9c2d81e47
Revises: e7df23ee8992
Create Date: 2026-06-19 23:30:00.000000

"""
from alembic import op

revision = 'a3f9c2d81e47'
down_revision = 'e7df23ee8992'
branch_labels = None
depends_on = None

CLINIC_SCOPED_TABLES = [
    "users", "patients", "appointments", "treatments", "treatment_plans",
    "invoices", "payment_plans", "consultorios", "appointment_types", "role_permissions",
]

# bypass_rls lets trusted internal code (migrations, seed scripts, the rare
# platform-wide lookup) opt out explicitly; everything else is fail-closed —
# an unset/garbage app.current_clinic_id matches nothing, not everything.
POLICY_EXPR = (
    "coalesce(current_setting('app.bypass_rls', true), 'off') = 'on' "
    "OR clinic_id = current_setting('app.current_clinic_id', true)::int"
)


def upgrade():
    for table in CLINIC_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE is required because table owners bypass RLS by default —
        # without it the policy below would be silently ignored for the
        # very role (dental_user, the migrations/owner role) most likely to
        # be misconfigured into runtime use.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY clinic_isolation ON {table} "
            f"USING ({POLICY_EXPR}) WITH CHECK ({POLICY_EXPR})"
        )


def downgrade():
    for table in CLINIC_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS clinic_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
