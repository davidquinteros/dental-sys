def iso_utc(dt):
    """Serializa un datetime naive-UTC como ISO-8601 con sufijo 'Z',
    para que `new Date()` en el frontend lo interprete como UTC (no local).
    Devuelve None si dt es None.

    Usar SOLO para campos "instante" (momentos precisos almacenados con
    `datetime.utcnow`). NO usar para `Appointment.scheduled_at` (hora local de
    pared), `Clinic.plan_started_at`/`plan_expires_at` (medianoche naive), ni
    para columnas `db.Date` (fecha-sola) — ver
    docs/superpowers/specs/2026-07-10-timezone-fix-design.md.
    """
    return dt.isoformat() + "Z" if dt else None
