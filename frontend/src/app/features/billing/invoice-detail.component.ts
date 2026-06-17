import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { BillingService } from '../../core/services/api.service';
import { Invoice } from '../../core/models';

@Component({
  selector: 'app-invoice-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './invoice-detail.component.html',
  styleUrl: './invoice-detail.component.css',
})
export class InvoiceDetailComponent implements OnInit {
  invoice = signal<Invoice | null>(null);
  loading = signal(true);
  paying = signal(false);
  payError = signal('');
  payMethod = 'cash';
  payReference = '';

  constructor(private route: ActivatedRoute, private billingService: BillingService) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.billingService.getInvoice(id).subscribe({
      next: res => { this.invoice.set(res.invoice); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  registerPayment(): void {
    const inv = this.invoice();
    if (!inv || inv.balance <= 0) return;
    this.paying.set(true);
    this.payError.set('');
    this.billingService.addPayment(inv.id, {
      amount: inv.balance,
      method: this.payMethod,
      reference: this.payReference || undefined,
    }).subscribe({
      next: res => {
        this.invoice.set(res.invoice);
        this.payReference = '';
        this.paying.set(false);
      },
      error: err => {
        this.payError.set(err.error?.error || 'Error al registrar pago');
        this.paying.set(false);
      },
    });
  }

  formatMoney(val: number): string {
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val || 0);
  }
  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'short', year: 'numeric' });
  }
  invStatusLabel(s: string): string {
    const m: Record<string, string> = { pending: 'Pendiente', paid: 'Pagada', cancelled: 'Cancelada', overdue: 'Vencida' };
    return m[s] ?? s;
  }
}
