/**
 * Formateo de fechas centralizado. Ver
 * docs/superpowers/specs/2026-07-10-timezone-fix-design.md
 *
 * - Instantes (backend con sufijo 'Z') y `scheduled_at` (hora local naive):
 *   usar `formatDate`/`formatDateLong`/`formatDateTime`/`formatTime` — `new Date`
 *   los interpreta correctamente.
 * - Campos `db.Date` ('YYYY-MM-DD', p.ej. date_of_birth, due_date, start_date):
 *   usar `formatDateOnly`, que NO aplica corrimiento de zona.
 */
const LOCALE = 'es-BO';

/** Instantes (con 'Z') y scheduled_at: día (mes corto). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' });
}

/** Instantes y scheduled_at: día (mes largo). */
export function formatDateLong(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(LOCALE, { day: '2-digit', month: 'long', year: 'numeric' });
}

/** Instantes y scheduled_at: día + hora. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
}

/** Instantes y scheduled_at: solo hora. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false });
}

/** Campos db.Date ('YYYY-MM-DD'): formatea SIN corrimiento de zona (mes corto). */
export function formatDateOnly(iso: string | null | undefined): string {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' });
}
