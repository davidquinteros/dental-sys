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

    db.create_all()
    print("Tablas creadas/verificadas.")
