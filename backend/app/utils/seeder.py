"""
Database seeder - Run with: flask seed
Creates initial admin user and sample data for development
"""
from app import db
from app.models.user import User, UserRole
from app.models.patient import Patient
from datetime import date


def seed_db():
    print("🌱 Seeding database...")

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
