from app import db
from datetime import datetime
from app.utils.serialization import iso_utc


class TreatmentImage(db.Model):
    """A clinical photo attached to a single appointment (Treatment) or to a
    whole TreatmentPlan.

    The bytes never live in this table — they're stored in a *private* Supabase
    Storage bucket (see app/utils/storage.py). This row only holds the object
    key (`storage_path`) plus metadata. Access is gated the same way as every
    other clinic-scoped table (ORM filter in middleware/tenancy.py + Postgres
    RLS), so the image bytes are only ever served back through an authenticated
    endpoint that first loads this row under the current clinic's scope — the
    bucket itself is never exposed publicly.
    """
    __tablename__ = "treatment_images"

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)

    # An image belongs to a single appointment (treatment) and/or a plan.
    # A photo taken during a session sets both; a plan-level photo (not tied to
    # a specific session) sets only treatment_plan_id.
    treatment_id = db.Column(db.Integer, db.ForeignKey("treatments.id"), nullable=True, index=True)
    treatment_plan_id = db.Column(db.Integer, db.ForeignKey("treatment_plans.id"), nullable=True, index=True)

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    storage_path = db.Column(db.String(512), nullable=False)   # object key inside the bucket
    content_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)           # bytes (post-compression)
    caption = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    clinic = db.relationship("Clinic")
    patient = db.relationship("Patient")
    treatment = db.relationship("Treatment")
    treatment_plan = db.relationship("TreatmentPlan")
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clinic_id": self.clinic_id,
            "patient_id": self.patient_id,
            "treatment_id": self.treatment_id,
            "treatment_plan_id": self.treatment_plan_id,
            "uploaded_by_id": self.uploaded_by_id,
            "uploaded_by_name": self.uploaded_by.full_name if self.uploaded_by else None,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "caption": self.caption,
            # Relative to environment.apiUrl on the frontend. The bytes are
            # streamed through this authenticated endpoint, never from a public
            # bucket URL — see routes/treatments.py::get_treatment_image_file.
            "file_url": f"/treatments/images/{self.id}/file",
            "created_at": iso_utc(self.created_at),
        }

    def __repr__(self):
        return f"<TreatmentImage #{self.id} - {self.storage_path}>"
