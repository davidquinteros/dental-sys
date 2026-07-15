import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { BillingService } from '../../core/services/api.service';
import { ConfirmService } from '../../core/services/confirm.service';
import { PaymentPlan, PaymentPlanInstallment } from '../../core/models';
import { formatDate as fmtDate, formatDateOnly as fmtDateOnly } from '../../core/util/date.util';

@Component({
  selector: 'app-payment-plan-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './payment-plan-detail.component.html',
  styleUrl: './payment-plan-detail.component.css',
})
export class PaymentPlanDetailComponent implements OnInit {
  plan = signal<PaymentPlan | null>(null);
  loading = signal(true);

  installments = signal<PaymentPlanInstallment[]>([]);
  loadingInstallments = signal(true);

  citasRows = signal<{ label: string; amount: number; status: 'paid' | 'partial' | 'pending'; paidAmount?: number }[]>([]);

  payType: 'inicial' | 'completo' | 'parcial' = 'completo';
  citasToRegister = 1;
  partialAmount = 0;
  initialAmount = 0;
  paymentNotes = '';
  paying = signal(false);
  payError = signal('');

  constructor(
    private route: ActivatedRoute,
    private billingService: BillingService,
    private confirmService: ConfirmService,
  ) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.load(id);
    this.loadInstallments(id);
  }

  load(id: number): void {
    this.billingService.getPaymentPlan(id).subscribe({
      next: res => {
        this.plan.set(res.payment_plan);
        this.buildCitasRows(res.payment_plan);
        this.citasToRegister = Math.min(1, this.maxCompleteCitas());
        this.partialAmount = 0;
        this.payType = this.downPaymentPending() ? 'inicial' : 'completo';
        this.initialAmount = this.pendingDownPayment();
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  loadInstallments(id: number): void {
    this.loadingInstallments.set(true);
    this.billingService.getPlanInstallments(id).subscribe({
      next: res => { this.installments.set(res.installments); this.loadingInstallments.set(false); },
      error: () => this.loadingInstallments.set(false),
    });
  }

  private buildCitasRows(p: PaymentPlan): void {
    const rows: { label: string; amount: number; status: 'paid' | 'partial' | 'pending'; paidAmount?: number }[] = [];
    if (p.down_payment > 0) {
      // The enganche is collected like any other payment, not pre-paid at creation.
      // The derivation attributes the first `down_payment` of total_paid to it, so it's
      // fully covered once total_paid >= down_payment, partial in between, else pending.
      if (p.total_paid >= p.down_payment) {
        rows.push({ label: 'Cuota inicial', amount: p.down_payment, status: 'paid' });
      } else if (p.total_paid > 0) {
        rows.push({ label: 'Cuota inicial', amount: p.down_payment, status: 'partial', paidAmount: p.total_paid });
      } else {
        rows.push({ label: 'Cuota inicial', amount: p.down_payment, status: 'pending' });
      }
    }
    for (let i = 1; i <= p.installments; i++) {
      if (i <= p.paid_installments) {
        rows.push({ label: `Cita ${i}`, amount: p.installment_amount, status: 'paid' });
      } else if (i === p.paid_installments + 1 && p.partial_progress_amount > 0) {
        rows.push({ label: `Cita ${i}`, amount: p.installment_amount, status: 'partial', paidAmount: p.partial_progress_amount });
      } else {
        rows.push({ label: `Cita ${i}`, amount: p.installment_amount, status: 'pending' });
      }
    }
    this.citasRows.set(rows);
  }

  /** Whether the enganche/pago inicial still has an outstanding balance — the "Pago
   * Inicial" toggle only makes sense (and is only shown) while this is true; once the
   * down payment is fully covered it disappears and only Completo/Parcial remain. */
  downPaymentPending(): boolean {
    const p = this.plan();
    return !!p && p.down_payment > 0 && p.total_paid < p.down_payment;
  }

  pendingDownPayment(): number {
    const p = this.plan();
    if (!p) return 0;
    return Math.round(Math.max(0, p.down_payment - p.total_paid) * 100) / 100;
  }

  selectPayType(type: 'inicial' | 'completo' | 'parcial'): void {
    this.payType = type;
    if (type === 'inicial') this.initialAmount = this.pendingDownPayment();
  }

  remainingCitas(): number {
    const p = this.plan();
    return p ? Math.max(0, p.installments - p.paid_installments) : 0;
  }

  maxCompleteCitas(): number {
    const p = this.plan();
    if (!p || !p.installment_amount) return 0;
    return Math.max(0, Math.floor((p.balance + 1e-6) / p.installment_amount));
  }

  registerPaymentAmount(): number {
    const p = this.plan();
    if (!p) return 0;
    return Math.round(this.citasToRegister * p.installment_amount * 100) / 100;
  }

  async registerPayment(): Promise<void> {
    const p = this.plan();
    if (!p || p.balance <= 0) return;

    let payload: { count?: number; amount?: number; notes?: string };
    let amount: number;
    if (this.payType === 'completo') {
      if (this.citasToRegister < 1 || this.citasToRegister > this.maxCompleteCitas()) return;
      payload = { count: this.citasToRegister };
      amount = this.registerPaymentAmount();
    } else if (this.payType === 'inicial') {
      if (this.initialAmount <= 0 || this.initialAmount > this.pendingDownPayment()) return;
      payload = { amount: this.initialAmount };
      amount = this.initialAmount;
    } else {
      if (this.partialAmount <= 0 || this.partialAmount > p.balance) return;
      payload = { amount: this.partialAmount };
      amount = this.partialAmount;
    }
    if (this.paymentNotes.trim()) payload.notes = this.paymentNotes.trim();

    const ok = await this.confirmService.confirm({
      title: 'Registrar pago',
      message: `¿Estás seguro de registrar el pago de "${p.name}" por Bs ${this.formatMoney(amount)}?`,
      confirmText: 'Registrar pago',
    });
    if (!ok) return;

    this.paying.set(true);
    this.payError.set('');
    this.billingService.registerInstallment(p.id, payload).subscribe({
      next: res => {
        this.plan.set(res.payment_plan);
        this.buildCitasRows(res.payment_plan);
        this.citasToRegister = Math.min(1, this.maxCompleteCitas());
        this.partialAmount = 0;
        this.payType = this.downPaymentPending() ? 'inicial' : 'completo';
        this.initialAmount = this.pendingDownPayment();
        this.paymentNotes = '';
        this.paying.set(false);
        this.loadInstallments(p.id);
      },
      error: err => {
        this.payError.set(err.error?.error || 'Error al registrar el pago');
        this.paying.set(false);
      },
    });
  }

  printPlan(): void {
    const p = this.plan();
    if (!p) return;
    window.open(`/billing/payment-plans/${p.id}/imprimir`, '_blank');
  }

  printReceipt(installmentId: number): void {
    const p = this.plan();
    if (!p) return;
    window.open(`/billing/payment-plans/${p.id}/comprobante/${installmentId}/imprimir`, '_blank');
  }

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  formatDate(iso?: string): string { return iso ? fmtDate(iso) : '—'; }
  formatDateOnly(iso?: string): string { return iso ? fmtDateOnly(iso) : '—'; }

  statusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', defaulted: 'En mora' };
    return m[s] ?? s;
  }
}
