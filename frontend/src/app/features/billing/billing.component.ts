import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { BillingService } from '../../core/services/api.service';
import { Invoice, PaymentPlan } from '../../core/models';

@Component({
  selector: 'app-billing',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './billing.component.html',
  styleUrl: './billing.component.css',
})
export class BillingComponent implements OnInit {
  view = signal<'invoices' | 'plans'>('invoices');
  invoices = signal<Invoice[]>([]);
  paymentPlans = signal<PaymentPlan[]>([]);
  summary = signal<any>(null);
  loadingInvoices = signal(true);
  loadingPlans = signal(true);
  statusFilter = signal('');

  statusFilters = [
    { value: '', label: 'Todas' },
    { value: 'pending', label: 'Pendientes' },
    { value: 'partial', label: 'Parciales' },
    { value: 'paid', label: 'Pagadas' },
    { value: 'overdue', label: 'Vencidas' },
  ];

  constructor(private billingService: BillingService) {}

  ngOnInit(): void {
    this.loadInvoices();
    this.loadPlans();
    this.billingService.getSummary().subscribe(res => this.summary.set(res));
  }

  loadInvoices(): void {
    this.loadingInvoices.set(true);
    const params: any = { per_page: 100 };
    if (this.statusFilter()) params.status = this.statusFilter();
    this.billingService.getInvoices(params).subscribe({
      next: res => { this.invoices.set(res.invoices); this.loadingInvoices.set(false); },
      error: () => this.loadingInvoices.set(false),
    });
  }

  loadPlans(): void {
    this.billingService.getPaymentPlans({ per_page: 100 }).subscribe({
      next: res => { this.paymentPlans.set(res.payment_plans); this.loadingPlans.set(false); },
      error: () => this.loadingPlans.set(false),
    });
  }

  filteredInvoices() { return this.invoices(); }

  activePlans(): number { return this.paymentPlans().filter(p => p.status === 'active').length; }

  registerInstallment(plan: PaymentPlan): void {
    this.billingService.registerInstallment(plan.id).subscribe({
      next: res => {
        this.paymentPlans.update(list => list.map(p => p.id === plan.id ? res.payment_plan : p));
        this.billingService.getSummary().subscribe(s => this.summary.set(s));
      },
    });
  }

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  invStatusLabel(s: string): string {
    const m: Record<string, string> = { pending: 'Pendiente', partial: 'Parcial', paid: 'Pagada', cancelled: 'Cancelada', overdue: 'Vencida' };
    return m[s] ?? s;
  }

  planStatusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', defaulted: 'En mora' };
    return m[s] ?? s;
  }
}
