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
session GUCs, applied below via a connection-pool checkout listener.
"""
from contextlib import contextmanager
from flask import g, has_app_context
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from sqlalchemy import event, text
from sqlalchemy.orm import Session, with_loader_criteria
from sqlalchemy.pool import Pool

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


# ─── Postgres session GUCs (RLS defense-in-depth) ───────────────────────────
#
# Earlier versions of this module set app.current_clinic_id / app.bypass_rls
# via db.session.execute(...) + db.session.commit() once per request. That's
# broken under real concurrency: SQLAlchemy's connection pool returns the
# DBAPI connection to the pool on every commit, and the *next* statement
# (even within the same request, e.g. re-reading a just-inserted row whose
# attributes were expired by that commit) may be handed a *different*
# physical connection — one whose GUCs belong to a different clinic, or none
# at all. Under gunicorn with multiple workers/threads this isn't a corner
# case, it's routine: it surfaced locally as `ObjectDeletedError` (RLS hiding
# a row this same request had just committed) the moment real concurrent
# requests were tested.
#
# Fix: re-apply the GUCs on *every* checkout from the pool, not once via a
# commit. `g` holds the current request's tenant context (set below by
# resolve_request_clinic, or by CLI commands via an app context); whichever
# physical connection gets handed out, it's stamped with whatever the
# *currently active* context is at that exact moment.
def _current_tenant_context():
    if not has_app_context():
        return NO_MATCH_CLINIC_ID, False
    return getattr(g, "clinic_id", NO_MATCH_CLINIC_ID), getattr(g, "rls_bypass", False)


@event.listens_for(Pool, "checkout")
def _stamp_tenant_guc_on_checkout(dbapi_connection, connection_record, connection_proxy):
    clinic_id, bypass = _current_tenant_context()
    cursor = dbapi_connection.cursor()
    try:
        # current_clinic_id is always a valid integer string, even when
        # unscoped (bypass=True covers actual access in that case) — the RLS
        # policy casts it with ::int, and '' raises InvalidTextRepresentation.
        # Postgres doesn't guarantee bypass_rls='on' short-circuits the policy's
        # OR before the ::int cast runs, so the right side must stay castable.
        cursor.execute(
            "SELECT set_config('app.bypass_rls', %s, false), "
            "set_config('app.current_clinic_id', %s, false)",
            ('on' if bypass else 'off', str(clinic_id) if clinic_id is not None else str(NO_MATCH_CLINIC_ID)),
        )
    finally:
        cursor.close()
    # is_local=false makes the setting outlive any transaction on this
    # connection, but the implicit transaction this SELECT opened (psycopg2
    # always opens one) should still be closed out before SQLAlchemy starts
    # using the connection for its own work.
    dbapi_connection.commit()


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

    # g.clinic_id is deliberately left unset (not even NO_MATCH_CLINIC_ID)
    # until we either resolve it or give up — _apply_clinic_filter treats an
    # unset g.clinic_id as "no filter" (matching its CLI/no-request-context
    # case), which is exactly what the bootstrap lookup below needs: at this
    # point we don't yet know the user's clinic, so the ORM-level filter must
    # not scope that lookup to anything, and RLS-level visibility is handled
    # by g.rls_bypass instead. Setting g.clinic_id to the fail-closed sentinel
    # *before* this lookup would scope it to "matches nothing" and hide the
    # user's own row.
    g.rls_bypass = False

    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if not user_id:
            g.clinic_id = NO_MATCH_CLINIC_ID
            return

        # Bootstrap lookup: we don't know this user's clinic yet, so there's
        # no value to scope this one query by. Bypass RLS just long enough
        # to read their own row.
        g.rls_bypass = True
        user = User.query.get(user_id)
        if not user:
            g.clinic_id = NO_MATCH_CLINIC_ID
            g.rls_bypass = False
            return

        if user.is_platform_admin:
            # Intentionally unscoped — platform staff operate across clinics.
            g.clinic_id = None
            g.rls_bypass = True
            return

        g.clinic_id = user.clinic_id if user.clinic_id is not None else NO_MATCH_CLINIC_ID
        g.rls_bypass = False
    except Exception:
        g.clinic_id = NO_MATCH_CLINIC_ID
        g.rls_bypass = False


@event.listens_for(Session, "do_orm_execute")
def _apply_clinic_filter(execute_state):
    if not execute_state.is_select:
        return

    if execute_state.execution_options.get("skip_clinic_filter"):
        # Explicit, rare opt-out for genuinely platform-wide lookups
        # (e.g. checking email uniqueness across all clinics at signup).
        return

    clinic_id = getattr(g, "clinic_id", None) if has_app_context() else None
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
