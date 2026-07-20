import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ReactiveFormsModule, FormBuilder, FormArray, FormGroup, Validators } from '@angular/forms';
import { BillingService } from '../../core/services/api.service';
import { ConfirmService } from '../../core/services/confirm.service';
import { Invoice } from '../../core/models';
import { formatDate as fmtDate, formatDateOnly as fmtDateOnly } from '../../core/util/date.util';

@Component({
  selector: 'app-invoice-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule, ReactiveFormsModule],
  templateUrl: './invoice-detail.component.html',
  styleUrl: './invoice-detail.component.css',
})
export class InvoiceDetailComponent implements OnInit {
  invoice = signal<Invoice | null>(null);
  loading = signal(true);
  paying = signal(false);
  payError = signal('');
  payType: 'completo' | 'parcial' = 'completo';
  payAmount = 0;
  payMethod = 'cash';
  payReference = '';

  editingItems = signal(false);
  itemsSaving = signal(false);
  itemsError = signal('');
  itemsForm: FormGroup;

  cancelling = signal(false);
  cancelError = signal('');

  constructor(
    private route: ActivatedRoute,
    private billingService: BillingService,
    private fb: FormBuilder,
    private confirmService: ConfirmService,
  ) {
    this.itemsForm = this.fb.group({ items: this.fb.array([]) });
  }

  get itemsArray(): FormArray { return this.itemsForm.get('items') as FormArray; }

  newItemGroup(item?: { description: string; quantity: number; unit_price: number }): FormGroup {
    return this.fb.group({
      description: [item?.description ?? '', Validators.required],
      quantity: [item?.quantity ?? 1, [Validators.required, Validators.min(1)]],
      unit_price: [item?.unit_price ?? 0, [Validators.required, Validators.min(0)]],
    });
  }

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.billingService.getInvoice(id).subscribe({
      next: res => {
        this.invoice.set(res.invoice);
        this.payAmount = res.invoice.balance;
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  startEditItems(): void {
    const inv = this.invoice();
    if (!inv) return;
    this.itemsArray.clear();
    inv.items.forEach(i => this.itemsArray.push(this.newItemGroup(i)));
    this.itemsError.set('');
    this.editingItems.set(true);
  }

  cancelEditItems(): void {
    this.editingItems.set(false);
  }

  addEditItem(): void { this.itemsArray.push(this.newItemGroup()); }
  removeEditItem(i: number): void { if (this.itemsArray.length > 1) this.itemsArray.removeAt(i); }

  editItemTotal(i: number): number {
    const item = this.itemsArray.at(i).value;
    return (item.quantity || 0) * (item.unit_price || 0);
  }

  editSubtotal(): number {
    return this.itemsArray.controls.reduce((s, _, i) => s + this.editItemTotal(i), 0);
  }

  saveItems(): void {
    const inv = this.invoice();
    if (!inv || this.itemsForm.invalid) return;
    this.itemsSaving.set(true);
    this.itemsError.set('');
    const items = this.itemsArray.value.map((item: any) => ({
      ...item,
      quantity: +item.quantity,
      unit_price: +item.unit_price,
    }));
    this.billingService.updateInvoice(inv.id, { items }).subscribe({
      next: res => {
        this.invoice.set(res.invoice);
        this.editingItems.set(false);
        this.itemsSaving.set(false);
      },
      error: err => {
        this.itemsError.set(err.error?.error || 'Error al guardar los ítems');
        this.itemsSaving.set(false);
      },
    });
  }

  async cancelInvoice(): Promise<void> {
    const inv = this.invoice();
    if (!inv || inv.status !== 'pending') return;
    const ok = await this.confirmService.confirm({
      title: 'Cancelar comprobante',
      message: `¿Cancelar el comprobante ${inv.invoice_number}? Esta acción no se puede deshacer.`,
      confirmText: 'Cancelar comprobante', cancelText: 'Volver', danger: true,
    });
    if (!ok) return;

    this.cancelling.set(true);
    this.cancelError.set('');
    this.billingService.updateInvoice(inv.id, { status: 'cancelled' }).subscribe({
      next: res => {
        this.invoice.set(res.invoice);
        this.cancelling.set(false);
      },
      error: err => {
        this.cancelError.set(err.error?.error || 'Error al cancelar el comprobante');
        this.cancelling.set(false);
      },
    });
  }

  registerPayment(): void {
    const inv = this.invoice();
    if (!inv || inv.balance <= 0) return;
    const amount = this.payType === 'completo' ? inv.balance : this.payAmount;
    if (amount <= 0 || amount > inv.balance) return;
    this.paying.set(true);
    this.payError.set('');
    this.billingService.addPayment(inv.id, {
      amount,
      method: this.payMethod,
      reference: this.payReference || undefined,
    }).subscribe({
      next: res => {
        this.invoice.set(res.invoice);
        this.payAmount = res.invoice.balance;
        this.payReference = '';
        this.paying.set(false);
      },
      error: err => {
        this.payError.set(err.error?.error || 'Error al registrar pago');
        this.paying.set(false);
      },
    });
  }

  printInvoice(): void {
    const inv = this.invoice();
    if (!inv) return;
    window.open(`/billing/invoices/${inv.id}/imprimir`, '_blank');
  }

  formatMoney(val: number): string {
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val || 0);
  }
  formatDate(iso: string): string { return fmtDate(iso); }
  formatDateOnly(iso: string): string { return fmtDateOnly(iso); }
  invStatusLabel(s: string): string {
    const m: Record<string, string> = { pending: 'Pendiente', partial: 'Parcial', paid: 'Pagada', cancelled: 'Cancelada', overdue: 'Vencida' };
    return m[s] ?? s;
  }
}
