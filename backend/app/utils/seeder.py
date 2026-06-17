"""
Database seeder - Run with: flask seed
Creates initial admin user, sample data, and standard app pages.
"""
from app import db
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.permission import Page, RolePermission
from datetime import date

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


def seed_pages():
    """Insert missing pages and their default role permissions."""
    added = 0
    for p_data in STANDARD_PAGES:
        viewers = p_data.pop('default_viewers')

        if not Page.query.filter_by(key=p_data['key']).first():
            page = Page(**p_data)
            db.session.add(page)
            db.session.flush()  # get the page into the session before FK refs

            # Create role_permissions for every role
            for role in UserRole:
                can_view = role.value in viewers
                rp = RolePermission(
                    role=role,
                    page_key=p_data['key'],
                    can_view=can_view,
                    can_create=can_view,
                    can_edit=can_view,
                    can_delete=role.value == 'ADMIN',
                )
                db.session.add(rp)

            added += 1
        else:
            # Page already exists — still ensure role_permissions rows exist
            for role in UserRole:
                exists = RolePermission.query.filter_by(
                    role=role, page_key=p_data['key']
                ).first()
                if not exists:
                    can_view = role.value in viewers
                    rp = RolePermission(
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


def seed_db():
    print("🌱 Seeding database...")

    # ─── Pages & permissions ────────────────────────────────────────────────
    seed_pages()

    # ─── Create users ───────────────────────────────────────────────────────
    if not User.query.filter_by(email="admin@clinica.com").first():
        admin = User(
            email="admin@clinica.com",
            first_name="Administrador",
            last_name="Sistema",
            role=UserRole.ADMIN,
        )
        admin.set_password("Admin2025!")
        db.session.add(admin)
        print("  ✓ Admin user created: admin@clinica.com / Admin2025!")

    if not User.query.filter_by(email="dr.garcia@clinica.com").first():
        doctor = User(
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

    if not User.query.filter_by(email="dr.morales@clinica.com").first():
        doctor2 = User(
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

    if not User.query.filter_by(email="recepcion@clinica.com").first():
        recep = User(
            email="recepcion@clinica.com",
            first_name="María",
            last_name="López",
            role=UserRole.RECEPTIONIST,
            phone="591-70055555",
        )
        recep.set_password("Recep2025!")
        db.session.add(recep)
        print("  ✓ Receptionist created: recepcion@clinica.com / Recep2025!")

    if not User.query.filter_by(email="asistente@clinica.com").first():
        asst = User(
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
    if Patient.query.count() == 0:
        patients = [
            Patient(
                first_name="Juan", last_name="Pérez",
                document_number="1234567",
                date_of_birth=date(1985, 3, 15),
                gender="M", phone="591-70011111",
                email="juan.perez@email.com",
                blood_type="O+", city="Santa Cruz de la Sierra",
            ),
            Patient(
                first_name="María", last_name="González",
                document_number="2345678",
                date_of_birth=date(1992, 7, 22),
                gender="F", phone="591-70022222",
                email="maria.g@email.com",
                blood_type="A+", city="Santa Cruz de la Sierra",
                allergies="Penicilina",
            ),
            Patient(
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


def register_seed_command(app):
    @app.cli.command("seed")
    def seed_command():
        """Seed the database with initial data"""
        with app.app_context():
            seed_db()
