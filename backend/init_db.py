"""Create/migrate database tables on container startup."""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Migrate appointment_type column from PostgreSQL ENUM to VARCHAR if needed
    with db.engine.connect() as conn:
        result = conn.execute(text("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'appointments' AND column_name = 'appointment_type'
        """))
        row = result.fetchone()
        if row and row[0] == 'USER-DEFINED':
            conn.execute(text("""
                ALTER TABLE appointments
                ALTER COLUMN appointment_type TYPE VARCHAR(100)
                USING appointment_type::text
            """))
            conn.commit()
            print("  ✓ appointment_type column migrated from ENUM to VARCHAR(100)")

    # Add medical_history column to patients if the table already exists without it
    with db.engine.connect() as conn:
        table_exists = conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'patients'"
        )).fetchone()
        if table_exists:
            conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS medical_history JSON"))
            conn.commit()

    db.create_all()
    print("Tablas creadas/verificadas.")
