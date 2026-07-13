import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { BillingService } from '../../core/services/api.service';
import { ConfirmService } from '../../core/services/confirm.service';
import { Budget } from '../../core/models';
import { formatDate as fmtDate, formatDateOnly as fmtDateOnly } from '../../core/util/date.util';

@Component({
  selector: 'app-budget-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './budget-detail.component.html',
  styleUrl: './budget-detail.component.css',
})
export class BudgetDetailComponent implements OnInit {
  budget = signal<Budget | null>(null);
  loading = signal(true);
  acting = signal(false);
  actionError = signal('');

  constructor(private route: ActivatedRoute, private billingService: BillingService, private confirmService: ConfirmService) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.load(id);
  }

  load(id: number): void {
    this.loading.set(true);
    this.billingService.getBudget(id).subscribe({
      next: res => { this.budget.set(res.budget); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  accept(): void {
    const b = this.budget();
    if (!b) return;
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
}
