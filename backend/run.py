from app import create_app, db
from app.utils.seeder import register_seed_command

app = create_app()
register_seed_command(app)


@app.shell_context_processor
def make_shell_context():
    from app.models import (
        User, Patient, Appointment, Treatment, TreatmentPlan,
        Invoice, Payment, PaymentPlan
    )
    return {
        "db": db,
        "User": User,
        "Patient": Patient,
        "Appointment": Appointment,
        "Treatment": Treatment,
        "TreatmentPlan": TreatmentPlan,
        "Invoice": Invoice,
        "Payment": Payment,
        "PaymentPlan": PaymentPlan,
    }


if __name__ == "__main__":
    app.run(debug=True, port=5000)
