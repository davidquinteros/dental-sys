import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormArray, FormGroup, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { BillingService, PatientService, TreatmentService } from '../../core/services/api.service';
import { Patient, TreatmentPlan } from '../../core/models';
import { BillingConditionsFieldsComponent } from '../../shared/components/billing-conditions-fields/billing-conditions-fields.component';

@Component({
  selector: 'app-budget-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink, BillingConditionsFieldsComponent],
  templateUrl: './budget-form.component.html',
  styleUrl: './budget-form.component.css',
})
export class BudgetFormComponent implements OnInit {
  form: FormGroup;
  saving = signal(false);
  errorMsg = signal('');
  selectedPatient = signal<Patient | null>(null);
  patientResults = signal<Patient[]>([]);
  treatmentPlans = signal<TreatmentPlan[]>([]);
  patientSearch = '';
  private searchTimeout: any;

  isEditMode = signal(false);
  private budgetId: number | null = null;

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private billingService: BillingService,
    private patientService: PatientService,
    private treatmentService: TreatmentService,
  ) {
    this.form = this.fb.group({
      name: ['', Validators.required],
      treatment_plan_id: [''],
      conditions: this.fb.group({
        calc_mode: ['total'],
        num_citas: [3, Validators.required],
        cost_per_cita: [0],
        total_amount: [0],
        down_payment: [0],
        start_date: [''],
        end_date: [''],
      }),
      items: this.fb.array([]),
      notes: [''],
    });
  }

  get conditionsGroup(): FormGroup {
    return this.form.get('conditions') as FormGroup;
  }

  get itemsArray(): FormArray {
    return this.form.get('items') as FormArray;
  }

  newItemGroup(item?: { description: string; quantity: number; unit_price: number }): FormGroup {
    return this.fb.group({
      description: [item?.description ?? '', Validators.required],
      quantity: [item?.quantity ?? 1, [Validators.required, Validators.min(1)]],
      unit_price: [item?.unit_price ?? 0, [Validators.required, Validators.min(0)]],
    });
  }

  addItem(): void { this.itemsArray.push(this.newItemGroup()); }
  removeItem(i: number): void { this.itemsArray.removeAt(i); }

  itemTotal(i: number): number {
    const item = this.itemsArray.at(i).value;
    return (item.quantity || 0) * (item.unit_price || 0);
  }

  itemsSubtotal(): number {
    return this.itemsArray.controls.reduce((s, _, i) => s + this.itemTotal(i), 0);
  }

  /** The presupuesto total is always the items subtotal — the Monto Total field is
   * read-only (see [totalReadonly] in the template). emitEvent:true so
   * billing-conditions-fields recomputes the derived cost-per-cita from the new total. */
  private syncTotalFromItems(): void {
    const subtotal = this.itemsSubtotal();
    this.conditionsGroup.get('total_amount')?.setValue(subtotal, { emitEvent: true });
  }

  ngOnInit(): void {
    this.itemsArray.valueChanges.subscribe(() => this.syncTotalFromItems());

    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.isEditMode.set(true);
      this.budgetId = +idParam;

      this.billingService.getBudget(this.budgetId).subscribe(res => {
        const budget = res.budget;
        if (budget.status !== 'draft') {
          this.router.navigate(['/billing/budgets', budget.id]);
          return;
        }
        this.patientService.getById(budget.patient_id).subscribe(pres => this.selectPatient(pres.patient, budget.treatment_plan_id));
        budget.items.forEach(item => this.itemsArray.push(this.newItemGroup(item)));
        this.form.patchValue({
          name: budget.name,
          treatment_plan_id: budget.treatment_plan_id || '',
          notes: budget.notes,
          conditions: {
            calc_mode: 'total',
            num_citas: budget.num_citas,
            down_payment: budget.down_payment,
            start_date: budget.start_date || '',
            end_date: budget.end_date || '',
          },
        });
        // Total is always derived from the items subtotal, not the stored value.
        this.syncTotalFromItems();
      });
      return;
    }

    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => this.selectPatient(res.patient));
    }
  }

  onPatientSearch(): void {
    clearTimeout(this.searchTimeout);
    if (!this.patientSearch || this.patientSearch.length < 2) { this.patientResults.set([]); return; }
    this.searchTimeout = setTimeout(() => {
      this.patientService.getAll({ search: this.patientSearch, per_page: 8 }).subscribe(
        res => this.patientResults.set(res.patients)
      );
    }, 300);
  }

  selectPatient(p: Patient, treatmentPlanId?: number): void {
    this.selectedPatient.set(p);
    this.patientResults.set([]);
    this.patientSearch = '';
    this.treatmentService.getPlans({ patient_id: p.id, status: 'active', per_page: 50 }).subscribe(
      res => this.treatmentPlans.set(res.treatment_plans)
    );
    if (treatmentPlanId) this.form.patchValue({ treatment_plan_id: treatmentPlanId });
  }

  clearPatient(): void {
    this.selectedPatient.set(null);
    this.treatmentPlans.set([]);
    this.form.patchValue({ treatment_plan_id: '' });
  }

  hasError(f: string): boolean { const c = this.form.get(f); return !!(c?.invalid && c?.touched); }

  onSubmit(): void {
    if (this.form.invalid || !this.selectedPatient()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const val = this.form.value;
    const cond = val.conditions;
    const items = (val.items || []).map((item: any) => ({
      description: item.description,
      quantity: +item.quantity,
      unit_price: parseFloat(item.unit_price),
    }));

    const payload: any = {
      patient_id: this.selectedPatient()!.id,
      treatment_plan_id: val.treatment_plan_id ? +val.treatment_plan_id : undefined,
      name: val.name,
      calc_mode: cond.calc_mode,
      num_citas: +cond.num_citas,
      down_payment: parseFloat(cond.down_payment) || 0,
      start_date: cond.start_date || undefined,
      end_date: cond.end_date || undefined,
      notes: val.notes || undefined,
      items,
    };
    if (cond.calc_mode === 'per_cita') {
      payload.cost_per_cita = parseFloat(cond.cost_per_cita) || 0;
    } else {
      payload.total_amount = parseFloat(cond.total_amount) || 0;
    }

    const request = this.isEditMode()
      ? this.billingService.updateBudget(this.budgetId!, payload)
      : this.billingService.createBudget(payload);

    request.subscribe({
      next: res => this.router.navigate(['/billing/budgets', res.budget.id]),
      error: err => { this.errorMsg.set(err.error?.error || 'Error al guardar el presupuesto'); this.saving.set(false); },
    });
  }
}
