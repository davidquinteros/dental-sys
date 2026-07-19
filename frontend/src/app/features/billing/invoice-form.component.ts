import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { BillingService, PatientService } from '../../core/services/api.service';
import { ConfirmService } from '../../core/services/confirm.service';
import { Budget, BudgetItem, BudgetItemBillingState, Patient } from '../../core/models';

@Component({
  selector: 'app-invoice-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
  templateUrl: './invoice-form.component.html',
  styleUrl: './invoice-form.component.css',
})
export class InvoiceFormComponent implements OnInit {
  form: FormGroup;
  saving = signal(false);
  errorMsg = signal('');
  selectedPatient = signal<Patient | null>(null);
  patientResults = signal<Patient[]>([]);
  patientSearch = '';
  private searchTimeout: any;

  /** Budget mode (FCLI-17): the comprobante charges items off a budget. The
   * patient comes from the budget and can't be changed, the "items" array holds
   * only the ADICIONALES, and the budget items are picked via checkboxes. */
  budget = signal<Budget | null>(null);
  selectedItemIds = signal<Set<number>>(new Set());
  isBudgetMode = computed(() => this.budget() !== null);

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private billingService: BillingService,
    private patientService: PatientService,
    private confirmService: ConfirmService,
  ) {
    this.form = this.fb.group({
      appointment_id: [''],
      due_date: [''],
      discount: [0],
      notes: [''],
      items: this.fb.array([this.newItem()]),
    });
  }

  get itemsArray(): FormArray { return this.form.get('items') as FormArray; }

  newItem(): FormGroup {
    return this.fb.group({
      description: ['', Validators.required],
      quantity: [1, [Validators.required, Validators.min(1)]],
      unit_price: [0, [Validators.required, Validators.min(0)]],
    });
  }

  ngOnInit(): void {
    const budgetId = this.route.snapshot.queryParamMap.get('budget_id');
    if (budgetId) {
      this.billingService.getBudget(+budgetId).subscribe({
        next: res => {
          this.budget.set(res.budget);
          this.patientService.getById(res.budget.patient_id).subscribe(p => this.selectedPatient.set(p.patient));
          // Extras start EMPTY here: the default blank row would be sent as a line
          // with no description and get rejected by the backend, and a budget
          // comprobante is perfectly valid with zero extras.
          this.itemsArray.clear();
          // Pre-select every pending item — charging what's left is the common case.
          this.selectedItemIds.set(new Set(
            res.budget.items!.filter(i => i.billing_state === 'pending').map(i => i.id!),
          ));
        },
        // Don't silently fall through to a plain comprobante form — that would
        // drop the budget link with no sign anything went wrong.
        error: () => this.errorMsg.set('No se pudo cargar el presupuesto. Volvé a Cobros e intentá de nuevo.'),
      });
      return;
    }

    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => this.selectedPatient.set(res.patient));
    }
    const appointmentId = this.route.snapshot.queryParamMap.get('appointment_id');
    if (appointmentId) this.form.patchValue({ appointment_id: +appointmentId });
  }

  // ── Budget item picker ──
  // Only a pending item can be charged onto a NEW comprobante. A 'billing' item
  // already sits on one — its remaining balance is collected THERE (charging it
  // again would double-charge and the backend rejects it), so it's not selectable
  // but stays actionable via a link. Only a fully 'paid' item is truly locked.
  isSelectable(item: BudgetItem): boolean { return item.billing_state === 'pending'; }
  isSelected(item: BudgetItem): boolean { return this.selectedItemIds().has(item.id!); }

  /** On a live comprobante that isn't fully paid — the balance is still collectable
   * (whether the comprobante is untouched or partially paid). */
  isCollectable(item: BudgetItem): boolean { return item.billing_state === 'billing'; }
  /** Fully paid: the only truly locked state. */
  isPaidOff(item: BudgetItem): boolean { return item.billing_state === 'paid'; }
  isPartiallyPaid(item: BudgetItem): boolean { return item.invoice_status === 'partial'; }

  async toggleItem(item: BudgetItem): Promise<void> {
    // Pending item: normal multi-select onto the NEW comprobante.
    if (this.isSelectable(item)) {
      const next = new Set(this.selectedItemIds());
      next.has(item.id!) ? next.delete(item.id!) : next.add(item.id!);
      this.selectedItemIds.set(next);
      return;
    }
    // Fully paid: locked — nothing left to collect.
    if (this.isPaidOff(item)) return;
    // Billing (issued / partially paid): its balance is completed on its OWN
    // comprobante, never re-charged here — take the user there.
    await this.goCollect(item);
  }

  /** Go to the item's comprobante to finish collecting its balance. Charging new
   * items and completing an existing partial payment are mutually exclusive in one
   * action, so if a new charge is already being built we warn first. */
  async goCollect(item: BudgetItem, ev?: Event): Promise<void> {
    ev?.stopPropagation();
    if (this.selectedItemIds().size > 0) {
      const proceed = await this.confirmService.confirm({
        title: 'Pago parcial pendiente',
        message: 'Hay un comprobante de pago con pago parcial pendiente. Completá el pago pendiente, '
          + 'o seleccioná solo el ítem para un nuevo pago.',
        confirmText: 'Ir a completar el pago',
        cancelText: 'Seguir con el nuevo ítem',
      });
      if (!proceed) return;
    }
    this.router.navigate(['/billing/invoices', item.invoice_id]);
  }

  selectedBudgetItems(): BudgetItem[] {
    return (this.budget()?.items ?? []).filter(i => this.isSelected(i));
  }

  itemStateLabel(s?: BudgetItemBillingState): string {
    const m: Record<BudgetItemBillingState, string> = {
      paid: '✓ Pagado', billing: '⏳ En cobro', pending: '○ Pendiente',
    };
    return s ? m[s] : '';
  }

  addItem(): void { this.itemsArray.push(this.newItem()); }
  /** In budget mode zero extras is valid; otherwise keep at least one line, since
   * that array is the whole comprobante. */
  removeItem(i: number): void {
    if (this.isBudgetMode() || this.itemsArray.length > 1) this.itemsArray.removeAt(i);
  }

  recalcItem(i: number): void { /* reactive, computed by getters */ }

  itemTotal(i: number): number {
    const item = this.itemsArray.at(i).value;
    return (item.quantity || 0) * (item.unit_price || 0);
  }

  extrasSubtotal(): number { return this.itemsArray.controls.reduce((s, _, i) => s + this.itemTotal(i), 0); }
  budgetItemsSubtotal(): number { return this.selectedBudgetItems().reduce((s, i) => s + i.total, 0); }
  subtotal(): number { return this.budgetItemsSubtotal() + this.extrasSubtotal(); }
  grandTotal(): number { return Math.max(0, this.subtotal() - (this.form.get('discount')?.value || 0)); }

  onSearch(): void {
    clearTimeout(this.searchTimeout);
    if (!this.patientSearch || this.patientSearch.length < 2) { this.patientResults.set([]); return; }
    this.searchTimeout = setTimeout(() => {
      this.patientService.getAll({ search: this.patientSearch, per_page: 8 }).subscribe(
        res => this.patientResults.set(res.patients)
      );
    }, 300);
  }

  selectPatient(p: Patient): void { this.selectedPatient.set(p); this.patientResults.set([]); this.patientSearch = ''; }
  clearPatient(): void { this.selectedPatient.set(null); }

  formatMoney(val: number): string {
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val || 0);
  }

  onSubmit(): void {
    if (!this.selectedPatient()) { this.errorMsg.set('Seleccione un paciente'); return; }
    // A comprobante needs at least one line, from either card.
    if (this.selectedBudgetItems().length + this.itemsArray.length === 0) {
      this.errorMsg.set('Seleccioná al menos un ítem del presupuesto o agregá un ítem adicional');
      return;
    }
    // Deliberately NOT short-circuiting on this.form.invalid: there is no
    // per-field error UI in this form, so an early return would make the button
    // a silent no-op (e.g. a blank extra-item description). Let it POST and
    // surface the backend's 400 in errorMsg, the way it worked before.
    this.saving.set(true);
    this.errorMsg.set('');
    const val = this.form.value;

    // Budget lines carry their budget_item_id and copy the budgeted
    // description/qty/price verbatim — they're read-only in the UI precisely so
    // the comprobante can't drift from what was proposed.
    const budgetLines = this.selectedBudgetItems().map(i => ({
      description: i.description,
      quantity: i.quantity,
      unit_price: i.unit_price,
      budget_item_id: i.id,
    }));
    const extras = (val.items || []).map((item: any) => ({
      description: item.description,
      quantity: +item.quantity,
      unit_price: +item.unit_price,
    }));

    const payload: any = {
      patient_id: this.selectedPatient()!.id,
      discount: +val.discount || 0,
      notes: val.notes || null,
      items: [...budgetLines, ...extras],
    };
    if (this.budget()) payload.budget_id = this.budget()!.id;
    if (val.appointment_id) payload.appointment_id = +val.appointment_id;
    if (val.due_date) payload.due_date = val.due_date;

    this.billingService.createInvoice(payload).subscribe({
      next: res => this.router.navigate(['/billing/invoices', res.invoice.id]),
      error: err => { this.errorMsg.set(err.error?.error || 'Error al crear el comprobante'); this.saving.set(false); },
    });
  }
}
