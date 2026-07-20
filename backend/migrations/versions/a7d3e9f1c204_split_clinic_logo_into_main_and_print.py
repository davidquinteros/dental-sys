"""Split Clinic.logo_url into logo_main_url (live app) and logo_print_url (documents)

FCLI-19: the single `logo_url` column only ever held the print/document logo. Rename
it to `logo_print_url` (preserving every existing value, so already-uploaded print
logos keep working) and add a nullable `logo_main_url` for the live-app/sidebar logo.

`clinics` is platform config, not tenant-scoped, so there are no RLS/`_scoped_models()`
changes here.

Revision ID: a7d3e9f1c204
Revises: f4c2b9a17d3e
Create Date: 2026-07-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7d3e9f1c204'
down_revision = 'f4c2b9a17d3e'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('clinics', 'logo_url', new_column_name='logo_print_url')
    op.add_column('clinics', sa.Column('logo_main_url', sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column('clinics', 'logo_main_url')
    op.alter_column('clinics', 'logo_print_url', new_column_name='logo_url')
