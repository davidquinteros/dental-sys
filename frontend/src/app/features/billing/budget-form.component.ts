import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormArray, FormGroup, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DestroyRef, inject } from '@angular/core';
import { BillingService, PatientService, TreatmentService, UserService } from '../../core/services/api.service';
import { Patient, TreatmentPlan, User } from '../../core/models';
import { BillingConditionsFieldsComponent } from '../../shared/components/billing-conditions-fields/billing-conditions-fields.component';
import { TREATMENT_TYPES, DEFAULT_TREATMENT_TYPE, treatmentTypeLabel } from '../treatments/treatment-type-data';

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
  itemsError = signal(false);
  selectedPatient = signal<Patient | null>(null);
  patientResults = signal<Patient[]>([]);
  treatmentPlans = signal<TreatmentPlan[]>([]);
  doctors = signal<User[]>([]);
  patientSearch = '';
  private searchTimeout: any;
  private destroyRef = inject(DestroyRef);

  readonly treatmentTypes = TREATMENT_TYPES;
  treatmentTypeLabel = treatmentTypeLabel;

  /** Drives the financing card's body. `use_payment_plan` is a TOP-LEVEL control,
   * not part of `conditions` — the conditions group must keep exactly the shape
   * billing-conditions-fields expects. */
  usePaymentPlan = signal(false);

  isEditMode = signal(false);
  private budgetId: number | null = null;

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private billingService: BillingService,
    private patientService: PatientService,
    private treatmentService: TreatmentService,
    private userService: UserService,
  ) {
    this.form = this.fb.group({
      name: ['', Validators.required],
      doctor_id: ['', Validators.required],
      treatment_type: [DEFAULT_TREATMENT_TYPE, Validators.required],
      tooth_number: [''],
      treatment_plan_id: [''],
      use_payment_plan: [false],
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

  addItem(): void { this.itemsArray.push(this.newItemGroup()); this.itemsError.set(false); }
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
    this.itemsArray.valueChanges.pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.syncTotalFromItems());
    this.form.get('use_payment_plan')!.valueChanges.pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(v => {
        this.usePaymentPlan.set(!!v);
        // The shared component derives in ngOnInit + a takeUntilDestroyed
        // subscription, so destroying and recreating it under the @if re-derives
        // cleanly — but only from a total that's already in sync.
        if (v) this.syncTotalFromItems();
      });
    // Solo médicos (rol DOCTOR): el médico responsable es una figura clínica, no un
    // admin. El backend valida el mismo conjunto — ver RESPONSIBLE_DOCTOR_ROLES.
    this.userService.getDoctors().subscribe(res => this.doctors.set(res.doctors));

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
        // getBudget (the detail endpoint) always sends items; only the list omits them.
        (budget.items ?? []).forEach(item => this.itemsArray.push(this.newItemGroup(item)));
        this.form.patchValue({
          name: budget.name,
          doctor_id: budget.doctor_id ?? '',
          treatment_type: budget.treatment_type || DEFAULT_TREATMENT_TYPE,
          tooth_number: budget.tooth_number || '',
          treatment_plan_id: budget.treatment_plan_id || '',
          use_payment_plan: budget.use_payment_plan,
          notes: budget.notes,
          conditions: {
            calc_mode: 'total',
            // An unfinanced budget stores NULL for the whole ladder; keep the
            // form's own defaults rather than pushing nulls into the controls.
            num_citas: budget.num_citas ?? 3,
            down_payment: budget.down_payment ?? 0,
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
    if (this.itemsArray.length === 0) { this.itemsError.set(true); }
    if (this.form.invalid || !this.selectedPatient() || this.itemsArray.length === 0) {
      this.form.markAllAsTouched();
      return;
    }
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
      doctor_id: +val.doctor_id,
      treatment_type: val.treatment_type,
      // null, not undefined: undefined is dropped by JSON.stringify, so the PUT
      // would never see the key and clearing the field on edit wouldn't persist.
      tooth_number: val.tooth_number || null,
      treatment_plan_id: val.treatment_plan_id ? +val.treatment_plan_id : null,
      name: val.name,
      use_payment_plan: !!val.use_payment_plan,
      // Always sent: total_amount is NOT NULL server-side and is the items subtotal.
      total_amount: this.itemsSubtotal(),
      notes: val.notes || undefined,
      items,
    };

    // conditions.num_citas keeps its required-with-default-3 validator, so the
    // form is valid with financing off — the fields just must not be SENT. The
    // backend NULLs them anyway; this keeps the request honest about intent.
    if (payload.use_payment_plan) {
      payload.calc_mode = cond.calc_mode;
      payload.num_citas = +cond.num_citas;
      payload.down_payment = parseFloat(cond.down_payment) || 0;
      payload.start_date = cond.start_date || undefined;
      payload.end_date = cond.end_date || undefined;
      if (cond.calc_mode === 'per_cita') {
        payload.cost_per_cita = parseFloat(cond.cost_per_cita) || 0;
      }
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
