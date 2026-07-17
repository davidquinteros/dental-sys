"""
Database seeder - Run with: flask seed
Creates initial admin user, sample data, and standard app pages.
"""
import click
from flask import g
from app import db
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.permission import Page, RolePermission
from datetime import date


def _bypass_rls():
    """CLI commands (flask seed, flask create-clinic) run outside any HTTP
    request, so there's no before_request hook to set the RLS session GUCs.
    These commands are trusted and need to see/write every clinic, so bypass
    RLS for the whole command rather than scoping per query.

    Setting g.rls_bypass (consumed by the connection-pool checkout listener
    in app.middleware.tenancy) rather than issuing `set_config` directly
    here is what makes this survive across the command's own commits — each
    one releases the connection back to the pool, and only the checkout
    listener is guaranteed to run again before the next statement."""
    g.rls_bypass = True
    g.clinic_id = None

# ── Icons stored as minimal SVG strings ──────────────────────────────────────

_ICON_DASHBOARD = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<rect x="3" y="3" width="7" height="7" rx="1"/>'
    '<rect x="14" y="3" width="7" height="7" rx="1"/>'
    '<rect x="14" y="14" width="7" height="7" rx="1"/>'
    '<rect x="3" y="14" width="7" height="7" rx="1"/>'
    '</svg>'
)
_ICON_PATIENTS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
    '<circle cx="9" cy="7" r="4"/>'
    '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
    '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
    '</svg>'
)
_ICON_APPOINTMENTS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<rect x="3" y="4" width="18" height="18" rx="2"/>'
    '<line x1="16" y1="2" x2="16" y2="6"/>'
    '<line x1="8" y1="2" x2="8" y2="6"/>'
    '<line x1="3" y1="10" x2="21" y2="10"/>'
    '</svg>'
)
_ICON_CALENDAR = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<rect x="3" y="4" width="18" height="18" rx="2"/>'
    '<line x1="16" y1="2" x2="16" y2="6"/>'
    '<line x1="8" y1="2" x2="8" y2="6"/>'
    '<line x1="3" y1="10" x2="21" y2="10"/>'
    '<circle cx="12" cy="16" r="1" fill="currentColor"/>'
    '</svg>'
)
_ICON_TREATMENTS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>'
    '</svg>'
)
_ICON_BILLING = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<line x1="12" y1="1" x2="12" y2="23"/>'
    '<path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'
    '</svg>'
)
_ICON_APPT_TYPES = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>'
    '<line x1="7" y1="7" x2="7.01" y2="7"/>'
    '</svg>'
)
_ICON_CONSULTORIOS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
    '<polyline points="9 22 9 12 15 12 15 22"/>'
    '</svg>'
)
_ICON_USERS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>'
    '<circle cx="12" cy="7" r="4"/>'
    '</svg>'
)
_ICON_PERMISSIONS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<rect x="3" y="11" width="18" height="11" rx="2"/>'
    '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    '</svg>'
)

# Pages ordered by sort_order — roles that CAN view each page by default
STANDARD_PAGES = [
    {
        'key': 'dashboard',
        'label': 'Dashboard',
        'route': '/dashboard',
        'sort_order': 10,
        'is_system': True,
        'icon': _ICON_DASHBOARD,
        'default_viewers': ['ADMIN', 'DOCTOR', 'RECEPTIONIST', 'ASSISTANT'],
    },
    {
        'key': 'patients',
        'label': 'Pacientes',
        'route': '/patients',
        'sort_order': 20,
        'is_system': True,
        'icon': _ICON_PATIENTS,
        'default_viewers': ['ADMIN', 'DOCTOR', 'RECEPTIONIST', 'ASSISTANT'],
    },
    {
        'key': 'appointments',
        'label': 'Citas',
        'route': '/appointments',
        'sort_order': 30,
        'is_system': True,
        'icon': _ICON_APPOINTMENTS,
        'default_viewers': ['ADMIN', 'DOCTOR', 'RECEPTIONIST', 'ASSISTANT'],
    },
    {
        'key': 'calendar',
        'label': 'Agenda',
        'route': '/calendar',
        'sort_order': 40,
        'is_system': True,
        'icon': _ICON_CALENDAR,
        'default_viewers': ['ADMIN', 'DOCTOR', 'RECEPTIONIST', 'ASSISTANT'],
    },
    {
        'key': 'treatments',
        'label': 'Atenciones',
        'route': '/treatments',
        'sort_order': 50,
        'is_system': True,
        'icon': _ICON_TREATMENTS,
        'default_viewers': ['ADMIN', 'DOCTOR', 'ASSISTANT'],
    },
    {
        'key': 'billing',
        'label': 'Cobros',
        'route': '/billing',
        'sort_order': 60,
        'is_system': True,
        'icon': _ICON_BILLING,
        'default_viewers': ['ADMIN', 'RECEPTIONIST'],
    },
    {
        'key': 'appointment_types',
        'label': 'Tipos de Cita',
        'route': '/appointment-types',
        'sort_order': 65,
        'is_system': True,
        'icon': _ICON_APPT_TYPES,
        'default_viewers': ['ADMIN'],
    },
    {
        'key': 'consultorios',
        'label': 'Consultorios',
        'route': '/consultorios',
        'sort_order': 70,
        'is_system': True,
        'icon': _ICON_CONSULTORIOS,
        'default_viewers': ['ADMIN'],
    },
    {
        'key': 'users',
        'label': 'Usuarios',
        'route': '/users',
        'sort_order': 80,
        'is_system': True,
        'icon': _ICON_USERS,
        'default_viewers': ['ADMIN'],
    },
    {
        'key': 'permissions',
        'label': 'Permisos',
        'route': '/permissions',
        'sort_order': 90,
        'is_system': True,
        'icon': _ICON_PERMISSIONS,
        'default_viewers': ['ADMIN'],
    },
]

ALL_ROLE_VALUES = [r.value for r in UserRole]


def seed_pages(clinic_id: int):
    """Insert missing pages (global) and this clinic's default role permissions."""
    added = 0
    for p_data in STANDARD_PAGES:
        viewers = p_data.pop('default_viewers')

        if not Page.query.filter_by(key=p_data['key']).first():
            page = Page(**p_data)
            db.session.add(page)
            db.session.flush()  # get the page into the session before FK refs
            added += 1

        # Ensure this clinic has a role_permissions row for every role on this page
        for role in UserRole:
            exists = RolePermission.query.filter_by(
                clinic_id=clinic_id, role=role, page_key=p_data['key']
            ).first()
            if not exists:
                can_view = role.value in viewers
                rp = RolePermission(
                    clinic_id=clinic_id,
                    role=role,
                    page_key=p_data['key'],
                    can_view=can_view,
                    can_create=can_view,
                    can_edit=can_view,
                    can_delete=role.value == 'ADMIN',
                )
                db.session.add(rp)

        # Put viewers back so the list is reusable if seed is called twice
        p_data['default_viewers'] = viewers

    if added:
        print(f"  ✓ {added} page(s) created")
    else:
        print("  ✓ Pages already seeded")


def seed_appointment_types(clinic_id: int):
    """Insert the built-in appointment types for this clinic if they don't exist yet."""
    from app.models.appointment_type import AppointmentTypeCatalog, BUILTIN_TYPES
    added = 0
    for t in BUILTIN_TYPES:
        exists = AppointmentTypeCatalog.query.filter_by(clinic_id=clinic_id, key=t['key']).first()
        if not exists:
            db.session.add(AppointmentTypeCatalog(clinic_id=clinic_id, **t))
            added += 1
    if added:
        print(f"  ✓ {added} appointment type(s) created")
    else:
        print("  ✓ Appointment types already seeded")


def seed_db(clinic_id: int = 1):
    print("🌱 Seeding database...")
    _bypass_rls()

    # ─── Clinic #1 (get-or-create) ──────────────────────────────────────────
    # En una base fresca la clínica demo no existe todavía y todo lo demás
    # (permisos, usuarios, pacientes) la referencia por FK — mismo patrón
    # get-or-create que seed_demo_clinic_b. En testing/prod ya existe y esto
    # es un no-op.
    from app.models.clinic import Clinic
    clinic = db.session.get(Clinic, clinic_id)
    if not clinic:
        clinic = Clinic(name="Clínica Demo", slug="clinica-demo")
        db.session.add(clinic)
        db.session.flush()  # get clinic.id
        clinic_id = clinic.id
        print(f"  ✓ Clínica Demo creada (id={clinic_id})")

    # ─── Pages & permissions ────────────────────────────────────────────────
    seed_pages(clinic_id)

    # ─── Appointment types ──────────────────────────────────────────────────
    seed_appointment_types(clinic_id)

    # ─── Create demo users (email is unique platform-wide) ─────────────────
    def _email_taken(email: str) -> bool:
        return User.query.filter_by(email=email).execution_options(skip_clinic_filter=True).first() is not None

    if not _email_taken("admin@clinica.com"):
        admin = User(
            clinic_id=clinic_id,
            email="admin@clinica.com",
            first_name="Administrador",
            last_name="Sistema",
            role=UserRole.ADMIN,
        )
        admin.set_password("Admin2025!")
        db.session.add(admin)
        print("  ✓ Admin user created: admin@clinica.com / Admin2025!")

    if not _email_taken("dr.garcia@clinica.com"):
        doctor = User(
            clinic_id=clinic_id,
            email="dr.garcia@clinica.com",
            first_name="Carlos",
            last_name="García",
            role=UserRole.DOCTOR,
            phone="591-70012345",
            specialty="Odontología General y Endodoncia",
            license_number="OD-2015-001",
        )
        doctor.set_password("Doctor2025!")
        db.session.add(doctor)
        print("  ✓ Doctor created: dr.garcia@clinica.com / Doctor2025!")

    if not _email_taken("dr.morales@clinica.com"):
        doctor2 = User(
            clinic_id=clinic_id,
            email="dr.morales@clinica.com",
            first_name="Ana",
            last_name="Morales",
            role=UserRole.DOCTOR,
            phone="591-70098765",
            specialty="Ortodoncia",
            license_number="OD-2018-042",
        )
        doctor2.set_password("Doctor2025!")
        db.session.add(doctor2)
        print("  ✓ Doctor created: dr.morales@clinica.com / Doctor2025!")

    if not _email_taken("recepcion@clinica.com"):
        recep = User(
            clinic_id=clinic_id,
            email="recepcion@clinica.com",
            first_name="María",
            last_name="López",
            role=UserRole.RECEPTIONIST,
            phone="591-70055555",
        )
        recep.set_password("Recep2025!")
        db.session.add(recep)
        print("  ✓ Receptionist created: recepcion@clinica.com / Recep2025!")

    if not _email_taken("asistente@clinica.com"):
        asst = User(
            clinic_id=clinic_id,
            email="asistente@clinica.com",
            first_name="Pedro",
            last_name="Vargas",
            role=UserRole.ASSISTANT,
            phone="591-70033333",
        )
        asst.set_password("Asist2025!")
        db.session.add(asst)
        print("  ✓ Assistant created: asistente@clinica.com / Asist2025!")

    # ─── Sample patients ────────────────────────────────────────────────────
    if Patient.query.filter_by(clinic_id=clinic_id).count() == 0:
        patients = [
            Patient(
                clinic_id=clinic_id,
                first_name="Juan", last_name="Pérez",
                document_number="1234567",
                date_of_birth=date(1985, 3, 15),
                gender="M", phone="591-70011111",
                email="juan.perez@email.com",
                blood_type="O+", city="Santa Cruz de la Sierra",
            ),
            Patient(
                clinic_id=clinic_id,
                first_name="María", last_name="González",
                document_number="2345678",
                date_of_birth=date(1992, 7, 22),
                gender="F", phone="591-70022222",
                email="maria.g@email.com",
                blood_type="A+", city="Santa Cruz de la Sierra",
                allergies="Penicilina",
            ),
            Patient(
                clinic_id=clinic_id,
                first_name="Roberto", last_name="Sánchez",
                document_number="3456789",
                date_of_birth=date(1978, 11, 5),
                gender="M", phone="591-70033334",
                blood_type="B+", city="Cochabamba",
            ),
        ]
        for p in patients:
            db.session.add(p)
        print(f"  ✓ {len(patients)} sample patients created")

    db.session.commit()
    print("✅ Seed completed!")


def seed_demo_clinic_b():
    """Second, smaller demo clinic — exists purely so the login page can show
    a real working "other clinic" login to demonstrate multi-tenant
    isolation, without anyone having to run `flask create-clinic` by hand.
    Idempotent like seed_db(), safe to call every time `flask seed` runs."""
    from app.models.clinic import Clinic

    _bypass_rls()
    clinic = Clinic.query.filter_by(slug="clinica-demo-b").first()
    if not clinic:
        clinic = Clinic(name="Clínica Demo B", slug="clinica-demo-b")
        db.session.add(clinic)
        db.session.flush()  # get clinic.id
        print("  ✓ Clínica Demo B creada")

    seed_pages(clinic.id)
    seed_appointment_types(clinic.id)

    def _email_taken(email: str) -> bool:
        return User.query.filter_by(email=email).execution_options(skip_clinic_filter=True).first() is not None

    if not _email_taken("admin@clinicab.com"):
        admin = User(
            clinic_id=clinic.id,
            email="admin@clinicab.com",
            first_name="Administradora",
            last_name="Demo B",
            role=UserRole.ADMIN,
        )
        admin.set_password("AdminB2025!")
        db.session.add(admin)
        print("  ✓ Admin user created: admin@clinicab.com / AdminB2025!")

    if Patient.query.filter_by(clinic_id=clinic.id).count() == 0:
        patients = [
            Patient(
                clinic_id=clinic.id,
                first_name="Lucía", last_name="Fernández",
                document_number="B-1000001",
                date_of_birth=date(1990, 5, 10),
                gender="F", phone="591-70099999",
                email="lucia.fernandez@email.com",
                blood_type="O+", city="La Paz",
            ),
            Patient(
                clinic_id=clinic.id,
                first_name="Diego", last_name="Castro",
                document_number="B-1000002",
                date_of_birth=date(1988, 9, 2),
                gender="M", phone="591-70088888",
                blood_type="A-", city="La Paz",
            ),
        ]
        for p in patients:
            db.session.add(p)
        print(f"  ✓ {len(patients)} sample patient(s) created (Clínica Demo B)")

    db.session.commit()


def create_clinic(name: str, admin_email: str, admin_password: str,
                   admin_first_name: str, admin_last_name: str,
                   subscription_tier_id: int | None = None) -> "Clinic":
    """Onboard a new clinic: the clinic row, its pages/permissions/appointment
    types (same defaults as any clinic), and its first admin user. No demo
    data — that's only for the bundled seed clinic."""
    from app.models.clinic import Clinic
    from app.models.subscription import SubscriptionStatus
    from datetime import datetime, timedelta
    import re

    _bypass_rls()
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    base_slug = slug
    n = 1
    while Clinic.query.filter_by(slug=slug).first():
        n += 1
        slug = f"{base_slug}-{n}"

    if subscription_tier_id is None:
        # New clinics start on the "trial" tier (same limits/features as
        # Profesional, $0) until a platform admin assigns a real paid tier
        # when converting them — the create-clinic form can still override
        # this by picking a tier up front.
        from app.models.subscription import SubscriptionTier
        trial_tier = SubscriptionTier.query.filter_by(code="trial").first()
        subscription_tier_id = trial_tier.id if trial_tier else None

    now = datetime.utcnow()
    clinic = Clinic(
        name=name, slug=slug,
        subscription_tier_id=subscription_tier_id,
        subscription_status=SubscriptionStatus.TRIAL,
        trial_ends_at=now + timedelta(days=30),
        plan_started_at=now,
        plan_expires_at=now + timedelta(days=30),
    )
    db.session.add(clinic)
    db.session.flush()  # get clinic.id

    seed_pages(clinic.id)
    seed_appointment_types(clinic.id)

    email = admin_email.strip().lower()
    if User.query.filter_by(email=email).execution_options(skip_clinic_filter=True).first():
        raise ValueError(f"El email '{email}' ya está registrado en otra clínica")

    admin = User(
        clinic_id=clinic.id,
        email=email,
        first_name=admin_first_name,
        last_name=admin_last_name,
        role=UserRole.ADMIN,
    )
    admin.set_password(admin_password)
    db.session.add(admin)
    db.session.commit()

    return clinic


def create_platform_admin(email: str, password: str, first_name: str, last_name: str) -> "User":
    """Bootstrap a platform-admin user (the SaaS operator, not a clinic admin).
    Not clinic-scoped: clinic_id stays None, same as how resolve_request_clinic
    recognizes is_platform_admin users at request time."""
    _bypass_rls()
    email = email.strip().lower()
    if User.query.filter_by(email=email).execution_options(skip_clinic_filter=True).first():
        raise ValueError(f"El email '{email}' ya está registrado")

    admin = User(
        clinic_id=None,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=UserRole.ADMIN,
        is_platform_admin=True,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin


def seed_subscription_tiers():
    """Idempotent: default SaaS plan tiers, looked up by `code`."""
    from app.models.subscription import SubscriptionTier

    _bypass_rls()
    defaults = [
        dict(name="Trial", code="trial", monthly_price=0, max_users=10,
             description="Período de prueba gratuito de 30 días, con las mismas funciones y el mismo límite de usuarios que el plan Profesional."),
        dict(name="Básico", code="basico", monthly_price=29, max_users=3,
             description="Hasta 3 usuarios. Ideal para consultorios pequeños."),
        dict(name="Profesional", code="profesional", monthly_price=59, max_users=10,
             description="Hasta 10 usuarios. Incluye calendario y odontograma."),
        dict(name="Premium", code="premium", monthly_price=99, max_users=None,
             description="Usuarios ilimitados y soporte prioritario."),
    ]
    for tier in defaults:
        if not SubscriptionTier.query.filter_by(code=tier["code"]).first():
            db.session.add(SubscriptionTier(**tier))
    db.session.commit()


def register_seed_command(app):
    @app.cli.command("seed")
    def seed_command():
        """Seed the database with initial data (clinic #1 + demo Clinic B)"""
        with app.app_context():
            seed_db()
            seed_demo_clinic_b()
            seed_subscription_tiers()

    @app.cli.command("create-platform-admin")
    @click.option("--email", required=True, help="Platform admin's email")
    @click.option("--password", required=True, help="Platform admin's password")
    @click.option("--first-name", default="Admin", help="Platform admin's first name")
    @click.option("--last-name", default="Plataforma", help="Platform admin's last name")
    def create_platform_admin_command(email, password, first_name, last_name):
        """Bootstrap a platform-admin user (the SaaS operator)"""
        with app.app_context():
            try:
                admin = create_platform_admin(email, password, first_name, last_name)
            except ValueError as e:
                print(f"  ✗ {e}")
                return
            print(f"  ✓ Platform admin created: {admin.email}")

    @app.cli.command("create-clinic")
    @click.option("--name", required=True, help="Clinic display name")
    @click.option("--admin-email", required=True, help="First admin user's email")
    @click.option("--admin-password", required=True, help="First admin user's password")
    @click.option("--admin-first-name", default="Admin", help="First admin user's first name")
    @click.option("--admin-last-name", default="", help="First admin user's last name")
    def create_clinic_command(name, admin_email, admin_password, admin_first_name, admin_last_name):
        """Onboard a new clinic (tenant) with its first admin user"""
        with app.app_context():
            try:
                clinic = create_clinic(name, admin_email, admin_password, admin_first_name, admin_last_name)
            except ValueError as e:
                print(f"  ✗ {e}")
                return
            print(f"  ✓ Clinic '{clinic.name}' created (id={clinic.id}, slug={clinic.slug})")
            print(f"  ✓ Admin user created: {admin_email}")
