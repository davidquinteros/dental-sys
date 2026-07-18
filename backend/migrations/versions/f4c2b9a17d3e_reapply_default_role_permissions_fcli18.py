"""Re-apply default role_permissions on clinics left all-false by the FCLI-18 casing bug

seed_pages() compared UserRole.value ('admin') against default_viewers holding role
NAMES ('ADMIN'), so it never matched: every clinic seeded before the fix has its whole
role_permissions matrix at false, leaving all non-admin staff with no access (admins are
unaffected — GET /permissions/me treats them apart). The seeder fix only helps NEW
clinics (seed_pages uses `if not exists`), so this migration repairs the existing ones.

Only clinics whose ENTIRE matrix is still all-false are touched — the all-false state is
the unmistakable fingerprint of the bug. A clinic where any flag is true was customized
by an admin by hand, so it's skipped to avoid clobbering that intent (FCLI-18 decision).

The role column is a Postgres `userrole` enum storing NAMES ('ADMIN', 'DOCTOR', ...),
hence the `role::text = :r` comparisons below.

Revision ID: f4c2b9a17d3e
Revises: e6a2c1f7b483
Create Date: 2026-07-17

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'f4c2b9a17d3e'
down_revision = 'e6a2c1f7b483'
branch_labels = None
depends_on = None


# Snapshot of STANDARD_PAGES' default_viewers at the time of FCLI-18 (role NAMES).
# Kept inline rather than imported from seeder.py so a later change to the seeder
# can't retroactively alter what this historical migration applied.
DEFAULT_VIEWERS = {
    'dashboard':         {'ADMIN', 'DOCTOR', 'RECEPTIONIST', 'ASSISTANT'},
    'patients':          {'ADMIN', 'DOCTOR', 'RECEPTIONIST', 'ASSISTANT'},
    'appointments':      {'ADMIN', 'DOCTOR', 'RECEPTIONIST', 'ASSISTANT'},
    'calendar':          {'ADMIN', 'DOCTOR', 'RECEPTIONIST', 'ASSISTANT'},
    'treatments':        {'ADMIN', 'DOCTOR', 'ASSISTANT'},
    'billing':           {'ADMIN', 'DOCTOR', 'RECEPTIONIST'},
    'appointment_types': {'ADMIN'},
    'consultorios':      {'ADMIN'},
    'users':             {'ADMIN'},
    'permissions':       {'ADMIN'},
}

ALL_ROLES = ('ADMIN', 'DOCTOR', 'RECEPTIONIST', 'ASSISTANT', 'GUEST')


def upgrade():
    conn = op.get_bind()

    # Clinics whose entire seeded matrix is still all-false => never customized.
    all_false_clinics = [
        row[0]
        for row in conn.execute(text(
            """
            SELECT clinic_id
            FROM role_permissions
            GROUP BY clinic_id
            HAVING bool_or(can_view OR can_create OR can_edit OR can_delete) = false
            """
        ))
    ]

    for clinic_id in all_false_clinics:
        for page_key, viewers in DEFAULT_VIEWERS.items():
            for role in ALL_ROLES:
                can_view = role in viewers
                can_delete = role == 'ADMIN'
                conn.execute(
                    text(
                        """
                        UPDATE role_permissions
                        SET can_view = :cv,
                            can_create = :cv,
                            can_edit = :cv,
                            can_delete = :cd
                        WHERE clinic_id = :c
                          AND page_key = :pk
                          AND role::text = :r
                        """
                    ),
                    {"cv": can_view, "cd": can_delete, "c": clinic_id, "pk": page_key, "r": role},
                )


def downgrade():
    # Not reversible: the prior per-clinic state (all-false due to the bug) isn't
    # tracked here, and reverting would only reinstate the broken permissions.
    pass
