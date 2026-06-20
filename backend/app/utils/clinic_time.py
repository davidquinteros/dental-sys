"""Clinic local-time helpers.

`Appointment.scheduled_at` (and the "today" boundaries derived from it) are
stored as naive datetimes representing local wall-clock time — the frontend
builds them with `toLocalIso()` (no UTC offset, no 'Z'), and `<input
type="datetime-local">` gives the browser's local time as-is. Comparing them
against `datetime.utcnow()` is wrong: the clinic's timezone (Bolivia,
UTC-4) means anything scheduled within ~4 hours from now would look like
it's "in the past" relative to UTC. Use `local_now()` / `local_today()`
wherever "now" needs to be compared against a stored local timestamp.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

CLINIC_TZ = ZoneInfo("America/La_Paz")


def local_now() -> datetime:
    """Naive 'now' in the clinic's local time zone, matching how `scheduled_at` is stored."""
    return datetime.now(CLINIC_TZ).replace(tzinfo=None)


def local_today():
    return local_now().date()
