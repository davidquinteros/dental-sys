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

This is mirrored at the Postgres level too (migration a3f9c2d81e47, Row Level
Security as defense-in-depth) via the app.current_clinic_id / app.bypass_rls
session GUCs set below.
"""
from contextlib import contextmanager
from flask import g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from sqlalchemy import event, text
from sqlalchemy.orm import Session, with_loader_criteria

NO_MATCH_CLINIC_ID = -1


@contextmanager
def platform_wide_lookup():
    """Scoped RLS bypass for the rare query that must legitimately see every
    clinic (e.g. checking email uniqueness platform-wide) without weakening
    isolation for the rest of the request. Runs inside a SAVEPOINT so the
    bypass setting (is_local=true) reverts the moment it's released, instead
    of leaking into whatever else the request's transaction still has to do.

    Pair with .execution_options(skip_clinic_filter=True) on the query
    itself to also skip the application-level ORM filter.
    """
    from app import db
    with db.session.begin_nested():
        db.session.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        yield


def _set_db_clinic_context(clinic_id, bypass: bool):
    """Mirror g.clinic_id into Postgres session settings so the RLS policies
    (defense-in-depth layer, see migration a3f9c2d81e47) see the same value
    the ORM-level filter is using.

    Deliberately session-scoped (is_local=false), not transaction-scoped:
    a single request can commit more than once (e.g. create_patient()
    commits, then to_dict() lazily reloads an expired attribute in a brand
    new autobegin transaction) — is_local=true would revert at that first
    commit and leave the rest of the request unscoped. reset_db_clinic_context
    (teardown_request) is what actually prevents this from leaking into the
    next request that reuses the same pooled connection.
    """
    from app import db
    db.session.execute(
        text("SELECT set_config('app.bypass_rls', :bypass, false), "
             "set_config('app.current_clinic_id', :cid, false)"),
        {"bypass": "on" if bypass else "off",
         "cid": str(clinic_id) if clinic_id is not None else ""},
    )
    db.session.commit()


def reset_db_clinic_context(*_args):
    """Flask teardown_request hook: force this connection back to fail-closed
    before it's returned to the pool, so the next request to reuse it (which
    may belong to a completely different user) never inherits this one's
    clinic context.

    A failed query earlier in the request can leave the transaction in
    Postgres's "aborted, commands ignored until rollback" state, so the
    set_config below would itself raise — roll back first to clear that,
    then retry once on a clean transaction.
    """
    from app import db
    for _attempt in range(2):
        try:
            db.session.execute(
                text("SELECT set_config('app.bypass_rls', 'off', false), "
                     "set_config('app.current_clinic_id', :cid, false)"),
                {"cid": str(NO_MATCH_CLINIC_ID)},
            )
            db.session.commit()
            return
        except Exception:
            db.session.rollback()


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
    """Flask before_request hook: resolve g.clinic_id from the JWT, if present.

    `verify_jwt_in_request(optional=True)` does not raise when no token is
    present (e.g. /auth/login itself, or a CORS preflight OPTIONS request),
    but it also leaves no JWT context behind — calling get_jwt_identity()
    afterwards would raise RuntimeError. So the whole resolution is wrapped,
    not just the verify call.
    """
    from app.models.user import User

    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if not user_id:
            _set_db_clinic_context(NO_MATCH_CLINIC_ID, bypass=False)
            return

        # Bootstrap lookup: we don't know this user's clinic yet, so there's
        # no value to scope this one query by. Bypass RLS just long enough
        # to read their own row (the application-level filter already skips
        # itself here too, since g.clinic_id isn't set until below).
        _set_db_clinic_context(NO_MATCH_CLINIC_ID, bypass=True)
        user = User.query.get(user_id)
        if not user:
            _set_db_clinic_context(NO_MATCH_CLINIC_ID, bypass=False)
            return

        if user.is_platform_admin:
            # Intentionally unscoped — platform staff operate across clinics.
            g.clinic_id = None
            _set_db_clinic_context(None, bypass=True)
            return

        g.clinic_id = user.clinic_id if user.clinic_id is not None else NO_MATCH_CLINIC_ID
        _set_db_clinic_context(g.clinic_id, bypass=False)
    except Exception:
        try:
            _set_db_clinic_context(NO_MATCH_CLINIC_ID, bypass=False)
        except Exception:
            pass
        return


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
