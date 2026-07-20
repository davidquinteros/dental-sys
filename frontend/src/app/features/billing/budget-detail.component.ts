import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { BillingService } from '../../core/services/api.service';
import { ConfirmService } from '../../core/services/confirm.service';
import { Budget, BudgetItemBillingState, Invoice } from '../../core/models';
import { formatDate as fmtDate, formatDateOnly as fmtDateOnly } from '../../core/util/date.util';
import { treatmentTypeLabel } from '../treatments/treatment-type-data';

@Component({
  selector: 'app-budget-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './budget-detail.component.html',
  styleUrl: './budget-detail.component.css',
})
export class BudgetDetailComponent implements OnInit {
  budget = signal<Budget | null>(null);
  invoices = signal<Invoice[]>([]);
  loading = signal(true);
  acting = signal(false);
  actionError = signal('');
  treatmentTypeLabel = treatmentTypeLabel;

  constructor(private route: ActivatedRoute, private billingService: BillingService, private confirmService: ConfirmService) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.load(id);
  }

  load(id: number): void {
    this.loading.set(true);
    this.billingService.getBudget(id).subscribe({
      next: res => { this.budget.set(res.budget); this.loading.set(false); this.loadInvoices(id); },
      error: () => this.loading.set(false),
    });
  }

  /** Comprobantes issued against this budget. Cheaper than a dedicated endpoint —
   * list_invoices just gained the budget_id filter. */
  private loadInvoices(id: number): void {
    this.billingService.getInvoices({ budget_id: id, per_page: 50 }).subscribe({
      next: res => this.invoices.set(res.invoices ?? []),
      error: () => this.invoices.set([]),
    });
  }

  /** Per-item value at budget price, as a % of the items subtotal. The three
   * segments are guaranteed by the backend to add up to exactly 100%. */
  segmentPct(state: BudgetItemBillingState): number {
    const b = this.budget();
    if (!b || !b.items_subtotal) return 0;
    const amount = state === 'paid' ? b.amount_paid : state === 'billing' ? b.amount_billed : b.amount_pending;
    return (amount / b.items_subtotal) * 100;
  }

  paidPct(): number { return Math.round(this.segmentPct('paid')); }

  /** Charging per item and financing are mutually exclusive, and financing stays
   * on the table only while nothing has been charged (mirrors link-plan's guard). */
  canFinance(): boolean {
    const b = this.budget();
    return !!b && b.status === 'accepted' && !b.use_payment_plan && !b.converted_plan_id && !b.has_billing;
  }

  canCharge(): boolean {
    const b = this.budget();
    return !!b && b.status === 'accepted' && !b.use_payment_plan && !b.converted_plan_id && !b.is_completed;
  }

  async accept(): Promise<void> {
    const b = this.budget();
    if (!b) return;
    // Accepting now writes a clinical record (the TreatmentPlan), so it asks
    // first — it used to fire on a single unconfirmed click.
    const doctor = b.doctor_name ? ` a nombre de ${b.doctor_name}` : '';
    const ok = await this.confirmService.confirm({
      title: 'Aceptar presupuesto',
      message: `Se creará automáticamente el plan de tratamiento «${b.name}»${doctor}, `
        + 'y el paciente podrá agendar sus citas contra él.',
      confirmText: 'Aceptar presupuesto',
    });
    if (!ok) return;
    this.acting.set(true);
    this.actionError.set('');
    this.billingService.acceptBudget(b.id).subscribe({
      next: res => { this.budget.set(res.budget); this.acting.set(false); },
      error: err => { this.actionError.set(err.error?.error || 'Error al aceptar'); this.acting.set(false); },
    });
  }

  async reject(): Promise<void> {
    const b = this.budget();
    if (!b) return;
    const ok = await this.confirmService.confirm({
      title: 'Rechazar presupuesto',
      message: '¿Rechazar este presupuesto? Esta acción no se puede deshacer.',
      confirmText: 'Rechazar', danger: true,
    });
    if (!ok) return;
    this.acting.set(true);
    this.actionError.set('');
    this.billingService.rejectBudget(b.id).subscribe({
      next: res => { this.budget.set(res.budget); this.acting.set(false); },
      error: err => { this.actionError.set(err.error?.error || 'Error al rechazar'); this.acting.set(false); },
    });
  }

  printBudget(): void {
    const b = this.budget();
    if (!b) return;
    window.open(`/billing/budgets/${b.id}/imprimir`, '_blank');
  }

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  formatDate(iso: string): string { return fmtDate(iso); }
  formatDateOnly(iso?: string): string { return iso ? fmtDateOnly(iso) : '—'; }

  statusLabel(s: string): string {
    const m: Record<string, string> = { draft: 'Borrador', accepted: 'Aceptado', rejected: 'Rechazado' };
    return m[s] ?? s;
  }

  itemStateLabel(s?: BudgetItemBillingState): string {
    const m: Record<BudgetItemBillingState, string> = {
      paid: '✓ Pagado', billing: '⏳ En cobro', pending: '○ Pendiente',
    };
    return s ? m[s] : '';
  }

  invStatusLabel(s: string): string {
    const m: Record<string, string> = {
      pending: 'Pendiente', partial: 'Parcial', paid: 'Pagado',
      cancelled: 'Anulado', overdue: 'Vencido',
    };
    return m[s] ?? s;
  }

  /** "1 (+1 adicional)" — how many budget items this comprobante charges, and
   * how many extras rode along. */
  invoiceItemsLabel(inv: Invoice): string {
    const fromBudget = inv.items.filter(i => i.budget_item_id != null).length;
    const extras = inv.items.length - fromBudget;
    return extras > 0 ? `${fromBudget} (+${extras} adicional${extras > 1 ? 'es' : ''})` : `${fromBudget}`;
  }
}
