/**
 * Formateo de fechas centralizado (admin-frontend). Ver
 * docs/superpowers/specs/2026-07-10-timezone-fix-design.md
 *
 * - Instantes (backend con sufijo 'Z') y datetimes naive a medianoche
 *   (plan_started_at/plan_expires_at): usar `formatDate`/`formatDateTime` —
 *   `new Date` los interpreta correctamente.
 * - Campos `db.Date` ('YYYY-MM-DD', p.ej. payment_date/period_start/period_end de
 *   SubscriptionPayment): usar `formatDateOnly`, sin corrimiento de zona.
 */
const LOCALE = 'es-BO';

/** Instantes (con 'Z') y datetimes naive: día (mes corto). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' });
}

/** Instantes y datetimes naive: día + hora. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
}

/** Campos db.Date ('YYYY-MM-DD'): formatea SIN corrimiento de zona (mes corto). */
export function formatDateOnly(iso: string | null | undefined): string {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' });
}
