"""optimize clinic_isolation RLS policy to avoid per-row re-evaluation

Revision ID: b7d924fa61ec
Revises: c8f5a2e91b4d
Create Date: 2026-07-10 00:00:00.000000

"""
from alembic import op

revision = 'b7d924fa61ec'
down_revision = 'c8f5a2e91b4d'
branch_labels = None
depends_on = None

# Every clinic_isolation policy (a3f9c2d81e47, f3f85dc00800, 22a40bfa3b04,
# d4e1f2a3b5c6) called current_setting(...) directly, which Postgres
# re-evaluates per row instead of once per query (Supabase's "Auth RLS
# Initialization Plan" advisor). Wrapping both calls in (select ...) lets the
# planner cache them as an initplan. Same policy name/shape everywhere — only
# the body expression changes.
CLINIC_SCOPED_TABLES = [
    "users", "patients", "appointments", "treatments", "treatment_plans",
    "invoices", "payment_plans", "consultorios", "appointment_types", "role_permissions",
    "subscription_payments", "payment_plan_installments", "treatment_images",
]

OLD_POLICY_EXPR = (
    "coalesce(current_setting('app.bypass_rls', true), 'off') = 'on' "
    "OR clinic_id = current_setting('app.current_clinic_id', true)::int"
)

NEW_POLICY_EXPR = (
    "coalesce((select current_setting('app.bypass_rls', true)), 'off') = 'on' "
    "OR clinic_id = (select current_setting('app.current_clinic_id', true))::int"
)


def upgrade():
    for table in CLINIC_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS clinic_isolation ON {table}")
        op.execute(
            f"CREATE POLICY clinic_isolation ON {table} "
            f"USING ({NEW_POLICY_EXPR}) WITH CHECK ({NEW_POLICY_EXPR})"
        )


def downgrade():
    for table in CLINIC_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS clinic_isolation ON {table}")
        op.execute(
            f"CREATE POLICY clinic_isolation ON {table} "
            f"USING ({OLD_POLICY_EXPR}) WITH CHECK ({OLD_POLICY_EXPR})"
        )
