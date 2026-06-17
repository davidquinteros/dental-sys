"""add consultorios table and consultorio_id to appointments

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-15 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'consultorios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('appointments',
        sa.Column('consultorio_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_appointments_consultorio_id',
        'appointments', 'consultorios',
        ['consultorio_id'], ['id'],
    )
    op.create_index('ix_appointments_consultorio_id', 'appointments', ['consultorio_id'])

    # Seed two default rooms
    op.execute("""
        INSERT INTO consultorios (name, description, color, is_active, created_at)
        VALUES
          ('Consultorio 1', 'Consultorio principal', '#4299e1', true, NOW()),
          ('Consultorio 2', 'Segundo consultorio', '#319795', true, NOW())
    """)


def downgrade():
    op.drop_index('ix_appointments_consultorio_id', table_name='appointments')
    op.drop_constraint('fk_appointments_consultorio_id', 'appointments', type_='foreignkey')
    op.drop_column('appointments', 'consultorio_id')
    op.drop_table('consultorios')
