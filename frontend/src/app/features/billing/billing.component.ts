import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { BillingService } from '../../core/services/api.service';
import { Invoice, PaymentPlan } from '../../core/models';
import { formatDate as fmtDate } from '../../core/util/date.util';

@Component({
  selector: 'app-billing',
  standalone: true,
  imports: [CommonModule, RouterLink],
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
    { value: 'paid', label: 'Pagadas' },
    { value: 'cancelled', label: 'Cancelada' },
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

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  formatDate(iso: string): string { return fmtDate(iso); }

  invStatusLabel(s: string): string {
    const m: Record<string, string> = { pending: 'Pendiente', paid: 'Pagada', cancelled: 'Cancelada', overdue: 'Vencida' };
    return m[s] ?? s;
  }

  planStatusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', defaulted: 'En mora' };
    return m[s] ?? s;
  }
}
