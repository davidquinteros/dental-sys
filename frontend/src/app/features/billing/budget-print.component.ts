import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { BillingService, PatientService, ClinicService } from '../../core/services/api.service';
import { Budget, BudgetItemBillingState, Invoice, Patient, ClinicInfo } from '../../core/models';
import { formatDate, formatDateLong, formatDateOnly } from '../../core/util/date.util';
import { PrintClinicHeaderComponent } from '../../shared/components/print-clinic-header/print-clinic-header.component';
import { treatmentTypeLabel } from '../treatments/treatment-type-data';

@Component({
  selector: 'app-budget-print',
  standalone: true,
  imports: [CommonModule, PrintClinicHeaderComponent],
  templateUrl: './budget-print.component.html',
  styleUrls: ['../../shared/styles/print-document.css', './budget-print.component.css'],
})
export class BudgetPrintComponent implements OnInit {
  loading = signal(true);
  error = signal('');
  budget = signal<Budget | null>(null);
  patient = signal<Patient | null>(null);
  clinic = signal<ClinicInfo | null>(null);
  citasRows = signal<{ label: string; amount: number }[]>([]);
  /** Comprobantes issued against this budget (per-item billing, FCLI-17). */
  invoices = signal<Invoice[]>([]);

  readonly issuedDate = formatDateLong(new Date().toISOString());
  treatmentTypeLabel = treatmentTypeLabel;

  constructor(
    private route: ActivatedRoute,
    private billingService: BillingService,
    private patientService: PatientService,
    private clinicService: ClinicService,
  ) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.billingService.getBudget(id).subscribe({
      next: res => {
        const budget = res.budget;
        this.budget.set(budget);
        this.buildCitasRows(budget);
        forkJoin({
          patient: this.patientService.getById(budget.patient_id),
          clinic: this.clinicService.getInfo(),
          invoices: this.billingService.getInvoices({ budget_id: id, per_page: 50 }),
        }).subscribe({
          next: ({ patient, clinic, invoices }) => {
            this.patient.set(patient.patient);
            this.clinic.set(clinic);
            this.invoices.set(invoices.invoices ?? []);
            this.loading.set(false);
          },
          error: () => { this.error.set('No se pudo cargar la información del presupuesto'); this.loading.set(false); },
        });
      },
      error: () => { this.error.set('Presupuesto no encontrado'); this.loading.set(false); },
    });
  }

  /** Only meaningful for a financed budget — an unfinanced one has NULL for the
   * whole ladder and the template renders a plain Total instead. Kept as this
   * component's own builder (payment-plan-print has its own on purpose — see
   * CLAUDE.md; do not merge them). */
  private buildCitasRows(b: Budget): void {
    if (!b.use_payment_plan) { this.citasRows.set([]); return; }
    const rows: { label: string; amount: number }[] = [];
    if ((b.down_payment ?? 0) > 0) {
      rows.push({ label: 'Cuota inicial', amount: b.down_payment! });
    }
    for (let i = 1; i <= (b.num_citas ?? 0); i++) {
      rows.push({ label: `Cita ${i}`, amount: b.cost_per_cita ?? 0 });
    }
    this.citasRows.set(rows);
  }

  /** Non-cancelled comprobantes: an anulado one returns its items to pending and
   * carries no money, so it's excluded from the money totals below. */
  private activeInvoices(): Invoice[] {
    return this.invoices().filter(i => i.status !== 'cancelled');
  }

  /** There's a real account state to print once any item sits on a live
   * comprobante (mirrors Budget.has_billing). Only then does the document switch
   * from the initial proposal to a statement. */
  hasBilling(): boolean {
    return !!this.budget()?.has_billing || this.activeInvoices().length > 0;
  }

  documentTitle(): string {
    return this.hasBilling() ? 'PRESUPUESTO — ESTADO DE CUENTA' : 'PRESUPUESTO';
  }

  /** Headline budget value (item subtotal at budget price). */
  budgetTotal(): number {
    return this.budget()?.items_subtotal ?? 0;
  }

  /** Actual cash received across every non-cancelled comprobante. */
  totalCollected(): number {
    return this.activeInvoices().reduce((s, i) => s + (i.amount_paid || 0), 0);
  }

  /** What's still owed on the whole budget: total minus cash collected. Adds up
   * with totalCollected() to the budget total, so the three cards reconcile. */
  pendingBalance(): number {
    return Math.max(0, this.budgetTotal() - this.totalCollected());
  }

  /** Outstanding balance on issued comprobantes (billed but not yet fully paid). */
  totalInvoiceBalance(): number {
    return this.activeInvoices().reduce((s, i) => s + (i.balance || 0), 0);
  }

  itemStateLabel(s?: BudgetItemBillingState): string {
    const m: Record<BudgetItemBillingState, string> = {
      paid: 'Pagado', billing: 'En cobro', pending: 'Pendiente',
    };
    return s ? m[s] : '—';
  }

  invStatusLabel(s: string): string {
    const m: Record<string, string> = {
      pending: 'Pendiente', partial: 'Parcial', paid: 'Pagado',
      cancelled: 'Anulado', overdue: 'Vencido',
    };
    return m[s] ?? s;
  }

  formatDate(iso?: string): string { return iso ? formatDate(iso) : '—'; }
  formatDateOnly(iso?: string): string { return iso ? formatDateOnly(iso) : '—'; }

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  print(): void {
    window.print();
  }
}
