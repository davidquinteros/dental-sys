"""close tenancy gap: add clinic_id to payments and invoice_items, add RLS

Revision ID: c3d67ef01a24
Revises: a1c56de89f03
Create Date: 2026-07-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d67ef01a24'
down_revision = 'a1c56de89f03'
branch_labels = None
depends_on = None

# payments and invoice_items predate multi-tenancy: they're tenant data (each
# row belongs to one clinic via its parent invoice) but never got a clinic_id
# column, so they were in neither enforcement layer (ORM filter in
# middleware/tenancy.py, RLS here) — see the "Known open gap" note in
# CLAUDE.md. Closing it the same way subscription_payments was closed after
# the fact (f3f85dc00800): add the column nullable, backfill from the parent
# invoice, then enforce NOT NULL + FK + the same clinic_isolation RLS policy
# as every other clinic-scoped table (already using the initplan-friendly
# (select ...) form fixed in b7d924fa61ec — no need to patch this one later).
TABLES = ["payments", "invoice_items"]

POLICY_EXPR = (
    "coalesce((select current_setting('app.bypass_rls', true)), 'off') = 'on' "
    "OR clinic_id = (select current_setting('app.current_clinic_id', true))::int"
)


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column('clinic_id', sa.Integer(), nullable=True))
        op.execute(
            f"UPDATE {table} SET clinic_id = invoices.clinic_id "
            f"FROM invoices WHERE invoices.id = {table}.invoice_id"
        )
        op.alter_column(table, 'clinic_id', nullable=False)
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_foreign_key(f'fk_{table}_clinic_id', 'clinics', ['clinic_id'], ['id'])
            batch_op.create_index(batch_op.f(f'ix_{table}_clinic_id'), ['clinic_id'], unique=False)

        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY clinic_isolation ON {table} "
            f"USING ({POLICY_EXPR}) WITH CHECK ({POLICY_EXPR})"
        )


def downgrade():
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS clinic_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(f'ix_{table}_clinic_id'))
            batch_op.drop_constraint(f'fk_{table}_clinic_id', type_='foreignkey')
        op.drop_column(table, 'clinic_id')
