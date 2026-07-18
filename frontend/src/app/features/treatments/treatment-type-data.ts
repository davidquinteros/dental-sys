/**
 * The treatment-type vocabulary, in one place (same reasoning as
 * odontogram-data.ts: the editor and the print view can't visually diverge if
 * they read the same array).
 *
 * Before FCLI-16 this list only existed as a hardcoded <select> in
 * treatment-plan-form.component.html, while five other places rendered
 * `plan.treatment_type` RAW. That worked only by accident — every value in the
 * select happened to be a word nobody looked at twice. Adding 'general' as the
 * default broke the accident: the UI would have shown the literal string
 * `general` everywhere. Anything that displays a treatment type must go through
 * treatmentTypeLabel().
 *
 * NOT to be confused with appointment types (patient-detail.typeLabel()): those
 * are a per-clinic catalog in the database (AppointmentTypeCatalog), a different
 * vocabulary. Backend-side nothing constrains this list — `treatment_type` is a
 * free String(100).
 */
export const TREATMENT_TYPES = [
  { value: 'general', label: 'Atención General' },
  { value: 'endodontics', label: 'Endodoncia' },
  { value: 'orthodontics', label: 'Ortodoncia' },
  { value: 'implant', label: 'Implante' },
  { value: 'periodontics', label: 'Periodoncia' },
  { value: 'prosthetics', label: 'Prótesis' },
  { value: 'surgery', label: 'Cirugía' },
  { value: 'whitening', label: 'Blanqueamiento' },
  { value: 'other', label: 'Otro' },
] as const;

/** The default for a new budget/plan — "Atención General". */
export const DEFAULT_TREATMENT_TYPE = 'general';

const LABELS: Record<string, string> = Object.fromEntries(
  TREATMENT_TYPES.map(t => [t.value, t.label]),
);

/**
 * Display label for a treatment type. Falls back to the raw value for rows
 * written before this list existed (or by an API client, since the column is
 * free text) — showing an unknown value is better than showing nothing.
 */
export function treatmentTypeLabel(value?: string | null): string {
  if (!value) return '—';
  return LABELS[value] ?? value;
}
