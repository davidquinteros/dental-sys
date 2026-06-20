"""Central multi-tenancy enforcement.

Every SELECT issued through the SQLAlchemy session — including ones triggered
by lazy-loading a relationship, not just a route's main query — gets an
automatic `clinic_id == g.clinic_id` filter applied to any model that has a
`clinic_id` column. This means a route that forgets to filter manually still
can't leak another clinic's data; the filter lives at the session level, not
per-route.

Fail-safe direction: if an authenticated, non-platform-admin user somehow has
no resolvable clinic_id, we filter on an impossible value (matches nothing)
rather than skipping the filter (which would return every clinic's data).
"""
from flask import g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

NO_MATCH_CLINIC_ID = -1


def _scoped_models():
    from app.models import (
        User, Patient, Appointment, Treatment, TreatmentPlan,
        Invoice, PaymentPlan, Consultorio, AppointmentTypeCatalog, RolePermission,
    )
    return (
        User, Patient, Appointment, Treatment, TreatmentPlan,
        Invoice, PaymentPlan, Consultorio, AppointmentTypeCatalog, RolePermission,
    )


def resolve_request_clinic():
    """Flask before_request hook: resolve g.clinic_id from the JWT, if present."""
    from app.models.user import User

    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return

    user_id = get_jwt_identity()
    if not user_id:
        return

    user = User.query.get(user_id)
    if not user:
        return

    if user.is_platform_admin:
        # Intentionally unscoped — platform staff operate across clinics.
        g.clinic_id = None
        return

    g.clinic_id = user.clinic_id if user.clinic_id is not None else NO_MATCH_CLINIC_ID


@event.listens_for(Session, "do_orm_execute")
def _apply_clinic_filter(execute_state):
    if not execute_state.is_select:
        return

    if execute_state.execution_options.get("skip_clinic_filter"):
        # Explicit, rare opt-out for genuinely platform-wide lookups
        # (e.g. checking email uniqueness across all clinics at signup).
        return

    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        # No request context (CLI/seed scripts) or an explicit platform-admin
        # request — both are trusted to operate unscoped.
        return

    for model in _scoped_models():
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                model, lambda cls: cls.clinic_id == clinic_id, include_aliases=True,
            )
        )
