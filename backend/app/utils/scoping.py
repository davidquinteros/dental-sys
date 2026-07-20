"""Safe resolution of client-sent foreign keys under multi-tenancy.

Why this exists: **Postgres does not apply RLS to foreign-key checks**, and the
ORM-level filter in `middleware/tenancy.py` only injects `clinic_id` into
SELECTs. So a `doctor_id`/`treatment_plan_id` belonging to another clinic
satisfies the FK constraint silently — neither enforcement layer catches it.

The rule these helpers encode: **never `setattr` a raw FK that came from the
client.** Resolve it through an ORM query first (which the tenancy filter scopes
to `g.clinic_id`), and treat "not found" as a 400/404. This is the same rule
`link_budget_plan` already follows for `payment_plan_id`.
"""
from app.models.user import User, UserRole
from app.models.treatment import TreatmentPlan

# Roles that may be a budget's / treatment plan's "médico responsable". Only the
# DOCTOR role qualifies — an admin is a management account, not a clinical one.
# Kept in sync with GET /users/doctors, which is what the budget and
# treatment-plan forms populate their dropdown from.
RESPONSIBLE_DOCTOR_ROLES = (UserRole.DOCTOR,)


def resolve_scoped_doctor(doctor_id):
    """Resolve a client-sent doctor_id into an active User of the CURRENT clinic
    who is allowed to be a responsible doctor.

    Returns None when the id is missing/malformed, belongs to another clinic, is
    inactive, or is held by someone whose role can't be a responsible doctor —
    callers turn that into a 400.
    """
    if doctor_id is None:
        return None
    try:
        doctor_id = int(doctor_id)
    except (TypeError, ValueError):
        return None
    doctor = User.query.filter_by(id=doctor_id, is_active=True).first()
    if doctor is None or doctor.role not in RESPONSIBLE_DOCTOR_ROLES:
        return None
    return doctor


def resolve_scoped_treatment_plan(plan_id, patient_id):
    """Resolve a client-sent treatment_plan_id, scoped to the current clinic, and
    confirm it belongs to `patient_id`.

    Returns None if it doesn't exist in this clinic or is another patient's plan.
    """
    if plan_id is None:
        return None
    try:
        plan_id = int(plan_id)
    except (TypeError, ValueError):
        return None
    plan = TreatmentPlan.query.filter_by(id=plan_id).first()
    if plan is None or plan.patient_id != int(patient_id):
        return None
    return plan
