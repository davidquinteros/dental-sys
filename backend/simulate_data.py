"""
Simulación de ~2 meses de operación de la clínica dental.
Crea médicos y pacientes adicionales, citas históricas y futuras,
atenciones clínicas, facturas/pagos y planes de tratamiento con sus
respectivos planes de pago.

Ejecutar dentro del contenedor backend:
    docker compose exec backend python simulate_data.py
"""
import random
import unicodedata
from datetime import date, datetime, time, timedelta

from app import create_app, db
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.treatment import Treatment, TreatmentPlan, TreatmentPlanStatus
from app.models.billing import (
    Invoice, InvoiceItem, Payment, PaymentMethod, PaymentPlan, PaymentPlanStatus,
)

random.seed(2025)

TODAY = date.today()
PAST_START = TODAY - timedelta(days=60)
FUTURE_END = TODAY + timedelta(days=9)

ALL_SLOTS = [(h, m) for h in range(8, 12) for m in (0, 30)] + \
            [(h, m) for h in range(14, 18) for m in (0, 30)]

FDI_TEETH = [str(n) for n in (
    list(range(11, 19)) + list(range(21, 29)) + list(range(31, 39)) + list(range(41, 49))
)]
SURFACES = ["M", "D", "O", "V", "L", "MO", "DO", "MOD"]
TOOTH_TYPES = {
    AppointmentType.FILLING, AppointmentType.EXTRACTION,
    AppointmentType.ENDODONTICS, AppointmentType.CROWN, AppointmentType.IMPLANT,
}

DURATIONS = {
    AppointmentType.CONSULTATION: [20, 30],
    AppointmentType.CLEANING: [30, 45],
    AppointmentType.EXTRACTION: [30, 45, 60],
    AppointmentType.FILLING: [30, 45, 60],
    AppointmentType.ENDODONTICS: [60, 90],
    AppointmentType.ORTHODONTICS: [20, 30],
    AppointmentType.IMPLANT: [60, 90, 120],
    AppointmentType.WHITENING: [45, 60],
    AppointmentType.CROWN: [45, 60],
    AppointmentType.FOLLOWUP: [15, 20, 30],
    AppointmentType.OTHER: [30, 45],
}

PRICES = {
    AppointmentType.CONSULTATION: (100, 150),
    AppointmentType.CLEANING: (150, 250),
    AppointmentType.EXTRACTION: (250, 450),
    AppointmentType.FILLING: (200, 400),
    AppointmentType.ENDODONTICS: (800, 1500),
    AppointmentType.ORTHODONTICS: (350, 550),
    AppointmentType.IMPLANT: (2500, 4500),
    AppointmentType.WHITENING: (450, 700),
    AppointmentType.CROWN: (1000, 1800),
    AppointmentType.FOLLOWUP: (0, 100),
    AppointmentType.OTHER: (100, 300),
}

PROCEDURE_NAMES = {
    AppointmentType.CONSULTATION: ["Consulta general", "Evaluación odontológica inicial", "Revisión periódica"],
    AppointmentType.CLEANING: ["Limpieza dental (profilaxis)", "Destartraje y pulido dental"],
    AppointmentType.EXTRACTION: ["Extracción simple", "Extracción de tercer molar"],
    AppointmentType.FILLING: ["Obturación con resina compuesta", "Restauración con amalgama"],
    AppointmentType.ENDODONTICS: ["Tratamiento de conducto", "Endodoncia monorradicular", "Endodoncia multirradicular"],
    AppointmentType.ORTHODONTICS: ["Control de ortodoncia", "Ajuste de brackets", "Cambio de arco de ortodoncia"],
    AppointmentType.IMPLANT: ["Colocación de implante dental", "Cirugía de implante", "Control post-implante"],
    AppointmentType.WHITENING: ["Blanqueamiento dental profesional"],
    AppointmentType.CROWN: ["Toma de impresión para corona", "Colocación de corona dental"],
    AppointmentType.FOLLOWUP: ["Control post-operatorio", "Revisión de evolución del tratamiento"],
    AppointmentType.OTHER: ["Procedimiento odontológico general"],
}

DIAGNOSES = {
    AppointmentType.CONSULTATION: ["Sin hallazgos relevantes", "Gingivitis leve", "Acumulación de placa bacteriana", "Sensibilidad dental generalizada"],
    AppointmentType.CLEANING: ["Sarro y placa bacteriana acumulada", "Gingivitis leve a moderada"],
    AppointmentType.EXTRACTION: ["Pieza con destrucción coronal extensa", "Tercer molar retenido/impactado", "Fractura dental no restaurable"],
    AppointmentType.FILLING: ["Caries dental clase I", "Caries dental clase II", "Caries oclusal moderada"],
    AppointmentType.ENDODONTICS: ["Pulpitis irreversible", "Necrosis pulpar", "Absceso periapical crónico"],
    AppointmentType.ORTHODONTICS: ["Maloclusión clase II", "Apiñamiento dentario", "Mordida cruzada anterior"],
    AppointmentType.IMPLANT: ["Edentulismo parcial", "Pérdida de pieza dental por extracción previa"],
    AppointmentType.WHITENING: ["Discromía dental por tinción extrínseca"],
    AppointmentType.CROWN: ["Pieza con tratamiento de conducto previo", "Fractura coronal restaurada"],
    AppointmentType.FOLLOWUP: ["Evolución favorable", "Cicatrización adecuada, sin complicaciones"],
    AppointmentType.OTHER: ["Evaluación general"],
}
GENERIC_DIAGNOSES = ["Sin hallazgos relevantes", "Evaluación general"]

CLINICAL_NOTES = [
    "Paciente tolera bien el procedimiento.",
    "Se indican cuidados post-operatorios.",
    "Sin complicaciones durante el procedimiento.",
    "Paciente refiere leve molestia, controlada con analgésicos.",
    "Se programa control en próxima cita.",
    "",
]

CANCELLATION_REASONS = [
    "Paciente solicitó reprogramación",
    "Paciente no pudo asistir por motivos laborales",
    "Cancelado por el paciente",
    "Reprogramado por disponibilidad del médico",
    "Paciente con cuadro de salud, reprograma",
]

DOCTOR_TYPE_WEIGHTS = {
    "dr.garcia@clinica.com": (
        [AppointmentType.CONSULTATION, AppointmentType.CLEANING, AppointmentType.FILLING,
         AppointmentType.ENDODONTICS, AppointmentType.EXTRACTION, AppointmentType.CROWN, AppointmentType.FOLLOWUP],
        [20, 18, 18, 14, 12, 10, 8],
    ),
    "dr.morales@clinica.com": (
        [AppointmentType.ORTHODONTICS, AppointmentType.CONSULTATION, AppointmentType.FOLLOWUP],
        [60, 25, 15],
    ),
    "dr.rojas@clinica.com": (
        [AppointmentType.IMPLANT, AppointmentType.EXTRACTION, AppointmentType.CONSULTATION,
         AppointmentType.OTHER, AppointmentType.FOLLOWUP],
        [25, 25, 25, 10, 15],
    ),
    "dra.quispe@clinica.com": (
        [AppointmentType.CONSULTATION, AppointmentType.CLEANING, AppointmentType.FILLING,
         AppointmentType.WHITENING, AppointmentType.FOLLOWUP],
        [35, 25, 25, 5, 10],
    ),
}

NEW_DOCTORS = [
    dict(email="dr.rojas@clinica.com", first_name="Fernando", last_name="Rojas",
         specialty="Cirugía Maxilofacial e Implantología", license_number="OD-2012-077",
         phone="591-70044556"),
    dict(email="dra.quispe@clinica.com", first_name="Lucía", last_name="Quispe",
         specialty="Odontopediatría", license_number="OD-2020-118",
         phone="591-70099887"),
]

# first_name, last_name, document_number, dob, gender, city, blood_type, allergies
NEW_PATIENTS = [
    ("Patricia", "Flores", "5000001", date(1990, 2, 14), "F", "La Paz", "A+", None),
    ("Jorge", "Mamani", "5000002", date(1975, 8, 30), "M", "El Alto", "O+", None),
    ("Carmen", "Quiroga", "5000003", date(1988, 12, 1), "F", "Santa Cruz de la Sierra", "B+", "Látex"),
    ("Luis", "Fernández", "5000004", date(1995, 5, 19), "M", "Cochabamba", "O-", None),
    ("Rosa", "Choque", "5000005", date(1982, 9, 9), "F", "La Paz", "A-", None),
    ("Miguel Ángel", "Torrez", "5000006", date(1970, 1, 25), "M", "Sucre", "AB+", None),
    ("Daniela", "Vargas", "5000007", date(2001, 3, 11), "F", "Santa Cruz de la Sierra", "O+", "Penicilina"),
    ("Andrés", "Salazar", "5000008", date(1993, 7, 7), "M", "Tarija", "B-", None),
    ("Verónica", "Paredes", "5000009", date(1986, 10, 23), "F", "Cochabamba", "A+", None),
    ("Ricardo", "Ortiz", "5000010", date(1979, 4, 2), "M", "Santa Cruz de la Sierra", "O+", None),
    ("Gabriela", "Mendoza", "5000011", date(1998, 11, 30), "F", "La Paz", "A+", None),
    ("Fernando", "Cáceres", "5000012", date(1965, 6, 18), "M", "Potosí", "B+", "Aspirina"),
    ("Lucía", "Aguilar", "5000013", date(1991, 2, 27), "F", "Santa Cruz de la Sierra", "O-", None),
    ("Diego", "Rojas", "5000014", date(2005, 9, 14), "M", "Cochabamba", "A+", None),
    ("Valeria", "Núñez", "5000015", date(1983, 12, 19), "F", "La Paz", "AB-", None),
    ("Sergio", "Guzmán", "5000016", date(1972, 3, 5), "M", "Santa Cruz de la Sierra", "O+", None),
    ("Camila", "Rivera", "5000017", date(2010, 7, 22), "F", "Cochabamba", "unknown", None),
    ("Oscar", "Medina", "5000018", date(1989, 1, 16), "M", "Santa Cruz de la Sierra", "A+", None),
    ("Natalia", "Vega", "5000019", date(1996, 8, 8), "F", "La Paz", "O+", None),
    ("Pablo", "Cordero", "5000020", date(1981, 5, 29), "M", "Sucre", "B+", None),
    ("Mariana", "Soliz", "5000021", date(1974, 10, 10), "F", "Santa Cruz de la Sierra", "A-", None),
    ("Eduardo", "Flores", "5000022", date(2008, 4, 12), "M", "Cochabamba", "O+", None),
    ("Sofía", "Ibáñez", "5000023", date(1992, 6, 25), "F", "La Paz", "A+", "Ibuprofeno"),
    ("Hugo", "Paz", "5000024", date(1968, 11, 3), "M", "Santa Cruz de la Sierra", "B-", None),
    ("Carla", "Roque", "5000025", date(1999, 2, 9), "F", "Tarija", "O-", None),
    ("Marco Antonio", "Espinoza", "5000026", date(1977, 7, 17), "M", "Cochabamba", "AB+", None),
    ("Daniela", "Fernández", "5000027", date(1990, 9, 21), "F", "Santa Cruz de la Sierra", "A+", None),
]


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower().replace(" ", "")


_invoice_seq = {}


def next_invoice_number(year: int) -> str:
    if year not in _invoice_seq:
        last = Invoice.query.filter(
            Invoice.invoice_number.like(f"INV-{year}-%")
        ).order_by(Invoice.id.desc()).first()
        _invoice_seq[year] = (int(last.invoice_number.split("-")[-1]) + 1) if last else 1
    seq = _invoice_seq[year]
    _invoice_seq[year] += 1
    return f"INV-{year}-{seq:04d}"


def create_invoice_with_payment(patient_id, appointment_id, items, created_at, receptionist_id):
    """items: list of (description, quantity, unit_price). Creates invoice, items and a
    randomized payment (full / partial / none)."""
    inv = Invoice(
        invoice_number=next_invoice_number(created_at.year),
        patient_id=patient_id,
        appointment_id=appointment_id,
        created_by_id=receptionist_id,
        due_date=(created_at + timedelta(days=15)).date(),
        created_at=created_at,
        updated_at=created_at,
        subtotal=0,
        discount=0,
        total=0,
        amount_paid=0,
        balance=0,
    )
    for desc, qty, price in items:
        inv.items.append(InvoiceItem(description=desc, quantity=qty, unit_price=price, total=qty * price))
    inv.recalculate()
    db.session.add(inv)
    db.session.flush()

    r = random.random()
    if r < 0.60:
        pay_amount = float(inv.total)
    elif r < 0.85:
        pay_amount = round(float(inv.total) * random.uniform(0.3, 0.7), 2)
    else:
        pay_amount = 0

    if pay_amount > 0:
        payment = Payment(
            invoice_id=inv.id,
            received_by_id=receptionist_id,
            amount=pay_amount,
            method=random.choice(list(PaymentMethod)),
            payment_date=created_at + timedelta(hours=random.randint(0, 3)),
            created_at=created_at,
        )
        db.session.add(payment)
        inv.amount_paid = pay_amount
        inv.recalculate()

    return inv


def run():
    app = create_app()
    with app.app_context():
        receptionist = User.query.filter_by(email="recepcion@clinica.com").first()

        # ── Doctors ──────────────────────────────────────────────────────
        for d in NEW_DOCTORS:
            if not User.query.filter_by(email=d["email"]).first():
                doc = User(
                    email=d["email"], first_name=d["first_name"], last_name=d["last_name"],
                    role=UserRole.DOCTOR, phone=d["phone"], specialty=d["specialty"],
                    license_number=d["license_number"],
                )
                doc.set_password("Doctor2025!")
                db.session.add(doc)
                print(f"  + Doctor creado: {d['email']}")
        db.session.commit()

        doctors = User.query.filter_by(role=UserRole.DOCTOR).order_by(User.id).all()

        # ── Patients ─────────────────────────────────────────────────────
        for i, (first, last, doc_num, dob, gender, city, blood, allergy) in enumerate(NEW_PATIENTS, start=1):
            if not Patient.query.filter_by(document_number=doc_num).first():
                p = Patient(
                    first_name=first, last_name=last, document_number=doc_num,
                    date_of_birth=dob, gender=gender, city=city, blood_type=blood,
                    phone=f"591-70{100000 + i:06d}",
                    email=f"{slugify(first.split()[0])}.{slugify(last.split()[0])}{i}@email.com",
                    allergies=allergy,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
                )
                db.session.add(p)
        db.session.commit()

        all_patients = Patient.query.order_by(Patient.id).all()
        print(f"  Total médicos: {len(doctors)}, total pacientes: {len(all_patients)}")

        # ── Appointments + Treatments + Invoices ────────────────────────
        appt_count = 0
        d_iter = PAST_START
        while d_iter <= FUTURE_END:
            if d_iter.weekday() < 5:  # weekdays only
                is_past = d_iter < TODAY
                for doctor in doctors:
                    n = random.randint(0, 3) if is_past else random.randint(0, 2)
                    if n == 0:
                        continue
                    types, weights = DOCTOR_TYPE_WEIGHTS.get(
                        doctor.email, DOCTOR_TYPE_WEIGHTS["dr.garcia@clinica.com"]
                    )
                    slots = random.sample(ALL_SLOTS, min(n, len(ALL_SLOTS)))
                    for (h, m) in slots:
                        patient = random.choice(all_patients)
                        appt_type = random.choices(types, weights=weights, k=1)[0]
                        duration = random.choice(DURATIONS[appt_type])
                        scheduled_at = datetime.combine(d_iter, time(h, m))
                        procedure_name = random.choice(PROCEDURE_NAMES[appt_type])

                        if is_past:
                            r = random.random()
                            if r < 0.80:
                                status = AppointmentStatus.COMPLETED
                            elif r < 0.92:
                                status = AppointmentStatus.CANCELLED
                            else:
                                status = AppointmentStatus.NO_SHOW
                        else:
                            status = random.choice([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED])

                        appt = Appointment(
                            patient_id=patient.id,
                            doctor_id=doctor.id,
                            created_by_id=receptionist.id,
                            scheduled_at=scheduled_at,
                            duration_minutes=duration,
                            appointment_type=appt_type,
                            status=status,
                            reason=procedure_name,
                            created_at=scheduled_at - timedelta(days=random.randint(1, 5)),
                        )
                        if status == AppointmentStatus.CANCELLED:
                            appt.cancellation_reason = random.choice(CANCELLATION_REASONS)
                        if status == AppointmentStatus.COMPLETED:
                            appt.completed_at = scheduled_at + timedelta(minutes=duration)

                        db.session.add(appt)
                        db.session.flush()
                        appt_count += 1

                        if status == AppointmentStatus.COMPLETED:
                            tooth = random.choice(FDI_TEETH) if appt_type in TOOTH_TYPES else None
                            surface = random.choice(SURFACES) if appt_type == AppointmentType.FILLING else None
                            treatment = Treatment(
                                patient_id=patient.id,
                                doctor_id=doctor.id,
                                appointment_id=appt.id,
                                diagnosis=random.choice(DIAGNOSES.get(appt_type, GENERIC_DIAGNOSES)),
                                procedure=procedure_name,
                                tooth_number=tooth,
                                tooth_surface=surface,
                                description=f"Procedimiento realizado: {procedure_name}.",
                                clinical_notes=random.choice(CLINICAL_NOTES),
                                performed_at=scheduled_at,
                                created_at=scheduled_at,
                                updated_at=scheduled_at,
                            )
                            db.session.add(treatment)

                            price_min, price_max = PRICES[appt_type]
                            unit_price = random.randint(price_min, price_max)
                            if unit_price > 0:
                                create_invoice_with_payment(
                                    patient.id, appt.id,
                                    [(procedure_name, 1, unit_price)],
                                    scheduled_at, receptionist.id,
                                )

                if appt_count % 100 == 0 and appt_count > 0:
                    db.session.commit()
            d_iter += timedelta(days=1)

        db.session.commit()
        print(f"  Citas creadas: {appt_count}")

        # ── Treatment Plans + Payment Plans ─────────────────────────────
        dr_garcia = next(d for d in doctors if d.email == "dr.garcia@clinica.com")
        dr_morales = next(d for d in doctors if d.email == "dr.morales@clinica.com")
        dr_rojas = next(d for d in doctors if d.email == "dr.rojas@clinica.com")

        by_doc = {p.document_number: p for p in all_patients}

        plans_spec = [
            dict(patient=by_doc["5000003"], doctor=dr_garcia, name="Endodoncia pieza 16",
                 ttype="endodontics", tooth="16", total=3, completed=3,
                 status=TreatmentPlanStatus.COMPLETED, start_offset=50, end_offset=10,
                 session_price=(800, 1200), payment_plan=None),
            dict(patient=by_doc["5000008"], doctor=dr_garcia, name="Endodoncia pieza 36",
                 ttype="endodontics", tooth="36", total=3, completed=2,
                 status=TreatmentPlanStatus.ACTIVE, start_offset=25, end_offset=None,
                 session_price=(800, 1200), payment_plan=None),
            dict(patient=by_doc["5000011"], doctor=dr_morales, name="Ortodoncia completa - Brackets metálicos",
                 ttype="orthodontics", tooth=None, total=12, completed=4,
                 status=TreatmentPlanStatus.ACTIVE, start_offset=58, end_offset=None,
                 session_price=None,
                 payment_plan=dict(total_amount=4500, down_payment=900, installments=12, paid_installments=4)),
            dict(patient=by_doc["5000021"], doctor=dr_morales, name="Ortodoncia completa - Brackets estéticos",
                 ttype="orthodontics", tooth=None, total=12, completed=1,
                 status=TreatmentPlanStatus.ACTIVE, start_offset=18, end_offset=None,
                 session_price=None,
                 payment_plan=dict(total_amount=5000, down_payment=1000, installments=12, paid_installments=1)),
            dict(patient=by_doc["5000016"], doctor=dr_rojas, name="Implante dental pieza 46",
                 ttype="implant", tooth="46", total=3, completed=2,
                 status=TreatmentPlanStatus.ACTIVE, start_offset=40, end_offset=None,
                 session_price=None,
                 payment_plan=dict(total_amount=3800, down_payment=1900, installments=3, paid_installments=1)),
            dict(patient=by_doc["5000024"], doctor=dr_rojas, name="Implante dental pieza 11",
                 ttype="implant", tooth="11", total=3, completed=3,
                 status=TreatmentPlanStatus.COMPLETED, start_offset=55, end_offset=5,
                 session_price=None,
                 payment_plan=dict(total_amount=4200, down_payment=1400, installments=3, paid_installments=3)),
        ]

        plan_count = 0
        for spec in plans_spec:
            start_date = TODAY - timedelta(days=spec["start_offset"])
            end_date = TODAY - timedelta(days=spec["end_offset"]) if spec["end_offset"] else None
            plan = TreatmentPlan(
                patient_id=spec["patient"].id,
                doctor_id=spec["doctor"].id,
                name=spec["name"],
                description=f"Plan de tratamiento: {spec['name']}.",
                treatment_type=spec["ttype"],
                status=spec["status"],
                total_sessions=spec["total"],
                completed_sessions=spec["completed"],
                tooth_number=spec["tooth"],
                start_date=start_date,
                estimated_end_date=start_date + timedelta(days=spec["total"] * 14),
                actual_end_date=end_date,
                notes=f"Seguimiento del tratamiento de {spec['ttype']}.",
                created_at=datetime.combine(start_date, time(9, 0)),
            )
            db.session.add(plan)
            db.session.flush()
            plan_count += 1

            span_end = end_date or TODAY
            span_days = max((span_end - start_date).days, 1)
            for s in range(spec["completed"]):
                performed_at = datetime.combine(
                    start_date + timedelta(days=int(span_days * (s + 1) / max(spec["total"], 1))),
                    time(random.choice([9, 10, 11, 15, 16]), random.choice([0, 30])),
                )
                appt_type = AppointmentType.ENDODONTICS if spec["ttype"] == "endodontics" else \
                    AppointmentType.ORTHODONTICS if spec["ttype"] == "orthodontics" else AppointmentType.IMPLANT
                treatment = Treatment(
                    patient_id=spec["patient"].id,
                    doctor_id=spec["doctor"].id,
                    treatment_plan_id=plan.id,
                    diagnosis=random.choice(DIAGNOSES[appt_type]),
                    procedure=f"{spec['name']} - Sesión {s + 1}/{spec['total']}",
                    tooth_number=spec["tooth"],
                    description=f"Sesión {s + 1} del plan '{spec['name']}'.",
                    clinical_notes=random.choice(CLINICAL_NOTES),
                    performed_at=performed_at,
                    created_at=performed_at,
                    updated_at=performed_at,
                )
                db.session.add(treatment)

                if spec["session_price"]:
                    price_min, price_max = spec["session_price"]
                    create_invoice_with_payment(
                        spec["patient"].id, None,
                        [(f"{spec['name']} - Sesión {s + 1}", 1, random.randint(price_min, price_max))],
                        performed_at, receptionist.id,
                    )

            pp = spec["payment_plan"]
            if pp:
                installment_amount = round((pp["total_amount"] - pp["down_payment"]) / pp["installments"], 2)
                total_paid = pp["down_payment"] + pp["paid_installments"] * installment_amount
                pp_status = PaymentPlanStatus.COMPLETED if spec["status"] == TreatmentPlanStatus.COMPLETED \
                    else PaymentPlanStatus.ACTIVE
                payment_plan = PaymentPlan(
                    patient_id=spec["patient"].id,
                    treatment_plan_id=plan.id,
                    created_by_id=receptionist.id,
                    name=f"Plan de pagos - {spec['name']}",
                    total_amount=pp["total_amount"],
                    down_payment=pp["down_payment"],
                    installments=pp["installments"],
                    installment_amount=installment_amount,
                    paid_installments=pp["paid_installments"],
                    total_paid=round(total_paid, 2),
                    status=pp_status,
                    start_date=start_date,
                    notes=f"Pago en {pp['installments']} cuotas mensuales.",
                    created_at=datetime.combine(start_date, time(9, 0)),
                )
                db.session.add(payment_plan)

        db.session.commit()
        print(f"  Planes de tratamiento creados: {plan_count}")
        print("✅ Simulación completada.")


if __name__ == "__main__":
    run()
