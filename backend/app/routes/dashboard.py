from flask import Blueprint, request, jsonify
from app import db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.patient import Patient
from app.models.billing import Invoice, InvoiceStatus
from app.models.treatment import TreatmentPlan
from app.models.user import UserRole
from app.middleware.auth import require_auth, get_current_user
from app.utils.clinic_time import local_today
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import joinedload

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
@require_auth
def get_dashboard():
    """
    Resumen del panel principal
    ---
    tags:
      - Dashboard
    security:
      - BearerAuth: []
    description: >
      Devuelve métricas operativas y financieras adaptadas al rol del usuario autenticado.
      Los médicos solo ven datos de sus propias citas y planes; los campos financieros y de
      pacientes (`monthly_revenue`, `monthly_pending_balance`, `total_patients`,
      `new_patients_this_month`) son `null` para roles que no sean admin o recepción.
    responses:
      200:
        description: Métricas del panel principal
        schema:
          type: object
          properties:
            today:
              type: object
              description: Citas del día actual
              properties:
                total:
                  type: integer
                  example: 8
                pending:
                  type: integer
                  description: Citas en estado scheduled o confirmed
                  example: 3
                appointments:
                  type: array
                  description: Hasta 10 citas del día
                  items:
                    $ref: '#/definitions/Appointment'
            week:
              type: object
              properties:
                total:
                  type: integer
                  description: Total de citas de la semana actual (excluye canceladas/no-show)
                  example: 32
            upcoming_7_days:
              type: integer
              description: Citas programadas/confirmadas en los próximos 7 días
              example: 21
            active_treatment_plans:
              type: integer
              example: 14
            monthly_revenue:
              type: number
              format: float
              x-nullable: true
              description: Monto cobrado en el mes actual (solo admin/recepción, null para otros roles)
              example: 18540.0
            monthly_pending_balance:
              type: number
              format: float
              x-nullable: true
              description: Saldo pendiente de facturas activas (solo admin/recepción, null para otros roles)
              example: 23928.0
            total_patients:
              type: integer
              x-nullable: true
              description: Total de pacientes activos (solo admin/recepción, null para otros roles)
              example: 187
            new_patients_this_month:
              type: integer
              x-nullable: true
              description: Pacientes nuevos registrados en el mes actual (solo admin/recepción, null para otros roles)
              example: 9
            calendar_appointments:
              type: array
              description: Citas de los próximos 7 días (no canceladas), máximo 50
              items:
                $ref: '#/definitions/Appointment'
            appointment_status_breakdown:
              type: object
              description: Conteo de citas por estado (claves según AppointmentStatus)
              additionalProperties:
                type: integer
              example:
                scheduled: 12
                confirmed: 8
                completed: 145
                cancelled: 6
                no_show: 3
      401:
        description: Token requerido o inválido
        schema:
          $ref: '#/definitions/Error'
    """
    current = get_current_user()
    today = local_today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    month_start = today.replace(day=1)

    # ─── Today's appointments ───────────────────────────────────────────────
    today_query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
    ).filter(
        Appointment.scheduled_at >= datetime.combine(today, datetime.min.time()),
        Appointment.scheduled_at <= datetime.combine(today, datetime.max.time()),
    )
    if current.role == UserRole.DOCTOR:
        today_query = today_query.filter_by(doctor_id=current.id)

    today_appointments = today_query.order_by(Appointment.scheduled_at).all()
    today_pending = [a for a in today_appointments if a.status in [
        AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED
    ]]

    # ─── Week appointments ──────────────────────────────────────────────────
    week_query = Appointment.query.filter(
        Appointment.scheduled_at >= datetime.combine(week_start, datetime.min.time()),
        Appointment.scheduled_at <= datetime.combine(week_end, datetime.max.time()),
        Appointment.status.not_in([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
    )
    if current.role == UserRole.DOCTOR:
        week_query = week_query.filter_by(doctor_id=current.id)
    week_total = week_query.count()

    # ─── Upcoming (next 7 days from today) ─────────────────────────────────
    upcoming_query = Appointment.query.filter(
        Appointment.scheduled_at > datetime.combine(today, datetime.max.time()),
        Appointment.scheduled_at <= datetime.combine(today + timedelta(days=7), datetime.max.time()),
        Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
    )
    if current.role == UserRole.DOCTOR:
        upcoming_query = upcoming_query.filter_by(doctor_id=current.id)

    # ─── Month revenue (admin/receptionist only) ────────────────────────────
    monthly_revenue = None
    monthly_pending = None
    if current.role in [UserRole.ADMIN, UserRole.RECEPTIONIST]:
        rev_result = db.session.query(func.sum(Invoice.amount_paid)).filter(
            Invoice.created_at >= datetime.combine(month_start, datetime.min.time()),
            Invoice.status != InvoiceStatus.CANCELLED,
        ).scalar()
        monthly_revenue = float(rev_result or 0)

        pending_result = db.session.query(func.sum(Invoice.balance)).filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIAL])
        ).scalar()
        monthly_pending = float(pending_result or 0)

    # ─── Patient stats (admin/receptionist) ────────────────────────────────
    total_patients = None
    new_patients_month = None
    if current.role in [UserRole.ADMIN, UserRole.RECEPTIONIST]:
        total_patients = Patient.query.filter_by(is_active=True).count()
        new_patients_month = Patient.query.filter(
            Patient.created_at >= datetime.combine(month_start, datetime.min.time()),
            Patient.is_active == True,
        ).count()

    # ─── Active treatment plans ─────────────────────────────────────────────
    active_plans_query = TreatmentPlan.query.filter_by(status="active")
    if current.role == UserRole.DOCTOR:
        active_plans_query = active_plans_query.filter_by(doctor_id=current.id)
    active_plans = active_plans_query.count()

    # ─── Calendar (today + next 6 days for logged doctor) ──────────────────
    calendar_appointments = []
    cal_start = datetime.combine(today, datetime.min.time())
    cal_end = datetime.combine(today + timedelta(days=6), datetime.max.time())
    cal_query = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.consultorio),
    ).filter(
        Appointment.scheduled_at >= cal_start,
        Appointment.scheduled_at <= cal_end,
        Appointment.status.not_in([AppointmentStatus.CANCELLED]),
    )
    if current.role == UserRole.DOCTOR:
        cal_query = cal_query.filter_by(doctor_id=current.id)
    calendar_appointments = [a.to_dict() for a in cal_query.order_by(Appointment.scheduled_at).limit(50)]

    # ─── Appointment status breakdown ──────────────────────────────────────
    breakdown_query = db.session.query(Appointment.status, func.count(Appointment.id))
    if current.role == UserRole.DOCTOR:
        breakdown_query = breakdown_query.filter(Appointment.doctor_id == current.id)
    breakdown_query = breakdown_query.group_by(Appointment.status)

    status_counts = {status.value: 0 for status in AppointmentStatus}
    for status, count in breakdown_query.all():
        status_counts[status.value] = count

    return jsonify({
        "today": {
            "total": len(today_appointments),
            "pending": len(today_pending),
            "appointments": [a.to_dict() for a in today_appointments[:10]],
        },
        "week": {
            "total": week_total,
        },
        "upcoming_7_days": upcoming_query.count(),
        "active_treatment_plans": active_plans,
        "monthly_revenue": monthly_revenue,
        "monthly_pending_balance": monthly_pending,
        "total_patients": total_patients,
        "new_patients_this_month": new_patients_month,
        "calendar_appointments": calendar_appointments,
        "appointment_status_breakdown": status_counts,
    }), 200
