import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { BillingService } from '../../core/services/api.service';
import { PaymentPlan, PaymentPlanInstallment } from '../../core/models';

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

  payAmount = 0;
  paying = signal(false);
  payError = signal('');

  constructor(private route: ActivatedRoute, private billingService: BillingService) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.load(id);
    this.loadInstallments(id);
  }

  load(id: number): void {
    this.billingService.getPaymentPlan(id).subscribe({
      next: res => {
        this.plan.set(res.payment_plan);
        this.payAmount = Math.min(res.payment_plan.installment_amount, res.payment_plan.balance);
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

  registerPayment(): void {
    const p = this.plan();
    if (!p || p.balance <= 0 || !this.payAmount || this.payAmount <= 0) return;
    this.paying.set(true);
    this.payError.set('');
    this.billingService.registerInstallment(p.id, this.payAmount).subscribe({
      next: res => {
        this.plan.set(res.payment_plan);
        this.payAmount = Math.min(res.payment_plan.installment_amount, res.payment_plan.balance);
        this.paying.set(false);
        this.loadInstallments(p.id);
      },
      error: err => {
        this.payError.set(err.error?.error || 'Error al registrar el pago');
        this.paying.set(false);
      },
    });
  }

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  formatDate(iso?: string): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  statusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', defaulted: 'En mora' };
    return m[s] ?? s;
  }
}
