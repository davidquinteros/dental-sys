"""add missing server defaults for is_active, subscription_status, is_platform_admin

Revision ID: a994a6c8d690
Revises: d4e1f2a3b5c6
Create Date: 2026-07-05 17:55:20.038297

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a994a6c8d690'
down_revision = 'd4e1f2a3b5c6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.alter_column('is_active', server_default=sa.true())
        batch_op.alter_column('subscription_status', server_default=sa.text("'TRIAL'::subscriptionstatus"))

    with op.batch_alter_table('consultorios', schema=None) as batch_op:
        batch_op.alter_column('is_active', server_default=sa.true())

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('is_platform_admin', server_default=sa.false())


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('is_platform_admin', server_default=None)

    with op.batch_alter_table('consultorios', schema=None) as batch_op:
        batch_op.alter_column('is_active', server_default=None)

    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.alter_column('subscription_status', server_default=None)
        batch_op.alter_column('is_active', server_default=None)
