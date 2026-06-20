"""add multi-tenancy clinic_id columns

Revision ID: e7df23ee8992
Revises: b2c3d4e5f6a7
Create Date: 2026-06-20 03:20:08.442562

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7df23ee8992'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None

# Tables that get a NOT NULL clinic_id (every row must belong to exactly one clinic).
REQUIRED_CLINIC_TABLES = [
    "patients", "appointments", "treatments", "treatment_plans",
    "invoices", "payment_plans", "consultorios", "appointment_types",
    "role_permissions",
]


def upgrade():
    # 1. New clinics table + the first clinic, so existing data has somewhere to point.
    op.create_table(
        'clinics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_clinics_slug', 'clinics', ['slug'], unique=True)
    op.execute("""
        INSERT INTO clinics (name, slug, is_active, created_at)
        VALUES ('Clinica Principal', 'clinica-principal', true, NOW())
    """)

    # 2. Add clinic_id (nullable for now) to every clinic-scoped table, backfill
    #    existing rows to clinic #1, then enforce NOT NULL once backfilled.
    for table in REQUIRED_CLINIC_TABLES:
        op.add_column(table, sa.Column('clinic_id', sa.Integer(), nullable=True))
        op.execute(f"UPDATE {table} SET clinic_id = 1")
        op.alter_column(table, 'clinic_id', nullable=False)
        op.create_index(f'ix_{table}_clinic_id', table, ['clinic_id'])
        op.create_foreign_key(f'fk_{table}_clinic_id', table, 'clinics', ['clinic_id'], ['id'])

    # users.clinic_id stays nullable — platform admins (us) don't belong to a clinic.
    op.add_column('users', sa.Column('clinic_id', sa.Integer(), nullable=True))
    op.execute("UPDATE users SET clinic_id = 1")
    op.add_column('users', sa.Column('is_platform_admin', sa.Boolean(), nullable=False, server_default='false'))
    op.create_index('ix_users_clinic_id', 'users', ['clinic_id'])
    op.create_foreign_key('fk_users_clinic_id', 'users', 'clinics', ['clinic_id'], ['id'])

    # 3. Replace global-uniqueness constraints with per-clinic composite ones.
    op.drop_index('ix_patients_document_number', table_name='patients')
    op.create_index('ix_patients_document_number', 'patients', ['document_number'])
    op.create_unique_constraint('uq_patient_clinic_document', 'patients', ['clinic_id', 'document_number'])

    op.drop_index('ix_invoices_invoice_number', table_name='invoices')
    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'])
    op.create_unique_constraint('uq_invoice_clinic_number', 'invoices', ['clinic_id', 'invoice_number'])

    op.drop_constraint('appointment_types_key_key', 'appointment_types', type_='unique')
    op.create_unique_constraint('uq_appttype_clinic_key', 'appointment_types', ['clinic_id', 'key'])

    op.drop_constraint('uq_role_page', 'role_permissions', type_='unique')
    op.create_unique_constraint('uq_role_page_clinic', 'role_permissions', ['clinic_id', 'role', 'page_key'])


def downgrade():
    op.drop_constraint('uq_role_page_clinic', 'role_permissions', type_='unique')
    op.create_unique_constraint('uq_role_page', 'role_permissions', ['role', 'page_key'])

    op.drop_constraint('uq_appttype_clinic_key', 'appointment_types', type_='unique')
    op.create_unique_constraint('appointment_types_key_key', 'appointment_types', ['key'])

    op.drop_constraint('uq_invoice_clinic_number', 'invoices', type_='unique')
    op.drop_index('ix_invoices_invoice_number', table_name='invoices')
    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'], unique=True)

    op.drop_constraint('uq_patient_clinic_document', 'patients', type_='unique')
    op.drop_index('ix_patients_document_number', table_name='patients')
    op.create_index('ix_patients_document_number', 'patients', ['document_number'], unique=True)

    op.drop_constraint('fk_users_clinic_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_clinic_id', table_name='users')
    op.drop_column('users', 'is_platform_admin')
    op.drop_column('users', 'clinic_id')

    for table in reversed(REQUIRED_CLINIC_TABLES):
        op.drop_constraint(f'fk_{table}_clinic_id', table, type_='foreignkey')
        op.drop_index(f'ix_{table}_clinic_id', table_name=table)
        op.drop_column(table, 'clinic_id')

    op.drop_index('ix_clinics_slug', table_name='clinics')
    op.drop_table('clinics')
