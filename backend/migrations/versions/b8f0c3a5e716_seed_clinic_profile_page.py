"""Seed the 'clinic_profile' page + its role_permissions for existing clinics (FCLI-20)

seed_pages() only runs at clinic creation / `flask seed`, so a newly-added STANDARD_PAGE
never reaches clinics that already exist. This backfills the new 'clinic_profile' page
(FCLI-19/22) so all staff of existing clinics can see it immediately.

These are brand-new rows (the page didn't exist before), so inserting the defaults can't
clobber any admin customization — unlike the FCLI-18 repair. Every insert is guarded by a
NOT EXISTS check for idempotency. The `role` column is the Postgres `userrole` enum, whose
values are NAMES ('ADMIN', 'DOCTOR', ...), hence the `::userrole` casts.

Revision ID: b8f0c3a5e716
Revises: a7d3e9f1c204
Create Date: 2026-07-17

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'b8f0c3a5e716'
down_revision = 'a7d3e9f1c204'
branch_labels = None
depends_on = None

PAGE_KEY = 'clinic_profile'
PAGE_LABEL = 'Perfil de la Clínica'
PAGE_ROUTE = '/clinic-profile'
PAGE_SORT_ORDER = 100
PAGE_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M3 21h18"/>'
    '<path d="M5 21V7l7-4 7 4v14"/>'
    '<path d="M10 12h4M12 10v4"/>'
    '</svg>'
)

# role NAME -> (can_view/create/edit, can_delete). Mirrors seed_pages() defaults for
# default_viewers = ADMIN/DOCTOR/RECEPTIONIST/ASSISTANT, can_delete only for ADMIN.
ROLE_FLAGS = {
    'ADMIN':        (True, True),
    'DOCTOR':       (True, False),
    'RECEPTIONIST': (True, False),
    'ASSISTANT':    (True, False),
    'GUEST':        (False, False),
}


def upgrade():
    conn = op.get_bind()

    conn.execute(
        text(
            """
            INSERT INTO pages (key, label, route, icon, is_system, sort_order, created_at)
            SELECT :key, :label, :route, :icon, true, :sort_order, now()
            WHERE NOT EXISTS (SELECT 1 FROM pages WHERE key = :key)
            """
        ),
        {"key": PAGE_KEY, "label": PAGE_LABEL, "route": PAGE_ROUTE,
         "icon": PAGE_ICON, "sort_order": PAGE_SORT_ORDER},
    )

    clinic_ids = [row[0] for row in conn.execute(text("SELECT id FROM clinics"))]
    for clinic_id in clinic_ids:
        for role, (can_view, can_delete) in ROLE_FLAGS.items():
            conn.execute(
                text(
                    """
                    INSERT INTO role_permissions
                        (clinic_id, role, page_key, can_view, can_create, can_edit, can_delete, updated_at)
                    SELECT :c, CAST(:r AS userrole), :pk, :cv, :cv, :cv, :cd, now()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM role_permissions
                        WHERE clinic_id = :c AND role::text = :r AND page_key = :pk
                    )
                    """
                ),
                {"c": clinic_id, "r": role, "pk": PAGE_KEY, "cv": can_view, "cd": can_delete},
            )


def downgrade():
    conn = op.get_bind()
    conn.execute(text("DELETE FROM role_permissions WHERE page_key = :pk"), {"pk": PAGE_KEY})
    conn.execute(text("DELETE FROM pages WHERE key = :pk"), {"pk": PAGE_KEY})
