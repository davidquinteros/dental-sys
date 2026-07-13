import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { BillingService, PatientService, TreatmentService } from '../../core/services/api.service';
import { Patient, TreatmentPlan } from '../../core/models';
import { BillingConditionsFieldsComponent } from '../../shared/components/billing-conditions-fields/billing-conditions-fields.component';
import { TreatmentPlanFormComponent } from '../treatments/treatment-plan-form.component';

@Component({
  selector: 'app-payment-plan-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink, BillingConditionsFieldsComponent, TreatmentPlanFormComponent],
  templateUrl: './payment-plan-form.component.html',
  styleUrl: './payment-plan-form.component.css',
})
export class PaymentPlanFormComponent implements OnInit {
  form: FormGroup;
  saving = signal(false);
  errorMsg = signal('');
  selectedPatient = signal<Patient | null>(null);
  patientResults = signal<Patient[]>([]);
  treatmentPlans = signal<TreatmentPlan[]>([]);
  patientSearch = '';
  private searchTimeout: any;

  isEditMode = signal(false);
  planTreatmentLabel = signal('');
  costLocked = signal(false);
  showPlanModal = signal(false);
  planModalPreset = signal<{ name?: string; start_date?: string; estimated_end_date?: string; total_sessions?: number }>({});
  private planId: number | null = null;
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
      treatment_plan_id: ['', Validators.required],
      conditions: this.fb.group({
        calc_mode: ['total'],
        num_citas: [3, Validators.required],
        cost_per_cita: [0],
        total_amount: [0],
        down_payment: [0],
        start_date: [''],
        end_date: [''],
      }),
      notes: [''],
    });
  }

  get conditionsGroup(): FormGroup {
    return this.form.get('conditions') as FormGroup;
  }

  ngOnInit(): void {
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.isEditMode.set(true);
      this.planId = +idParam;
      // Patient and treatment plan are fixed once a payment plan exists.
      this.form.get('treatment_plan_id')?.clearValidators();
      this.form.get('treatment_plan_id')?.updateValueAndValidity();

      this.billingService.getPaymentPlan(this.planId).subscribe(res => {
        const plan = res.payment_plan;
        this.planTreatmentLabel.set(plan.treatment_plan_name || `Plan #${plan.treatment_plan_id}`);
        this.costLocked.set(plan.paid_installments > 0);
        this.patientService.getById(plan.patient_id).subscribe(pres => this.selectedPatient.set(pres.patient));
        this.form.patchValue({
          name: plan.name,
          treatment_plan_id: plan.treatment_plan_id,
          notes: plan.notes,
          conditions: {
            calc_mode: 'total',
            num_citas: plan.installments,
            cost_per_cita: plan.installment_amount,
            total_amount: plan.total_amount,
            down_payment: plan.down_payment,
            start_date: plan.start_date || '',
            end_date: plan.end_date || '',
          },
        });
      });
      return;
    }

    const budgetId = this.route.snapshot.queryParamMap.get('budget_id');
    if (budgetId) {
      this.budgetId = +budgetId;
      this.billingService.getBudget(this.budgetId).subscribe(res => {
        const budget = res.budget;
        this.patientService.getById(budget.patient_id).subscribe(pres => this.selectPatient(pres.patient));
        this.form.patchValue({
          name: budget.name,
          conditions: {
            calc_mode: 'total',
            num_citas: budget.num_citas,
            cost_per_cita: budget.cost_per_cita,
            total_amount: budget.total_amount,
            down_payment: budget.down_payment,
            start_date: budget.start_date || '',
            end_date: budget.end_date || '',
          },
        });
      });
      return;
    }

    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => {
        this.selectPatient(res.patient);
      });
    }
    const planId = this.route.snapshot.queryParamMap.get('plan_id');
    if (planId) this.form.patchValue({ treatment_plan_id: +planId });
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

  selectPatient(p: Patient): void {
    this.selectedPatient.set(p);
    this.patientResults.set([]);
    this.patientSearch = '';
    // Load their active treatment plans
    this.treatmentService.getPlans({ patient_id: p.id, status: 'active', per_page: 50 }).subscribe(
      res => this.treatmentPlans.set(res.treatment_plans)
    );
  }

  clearPatient(): void {
    this.selectedPatient.set(null);
    this.treatmentPlans.set([]);
    this.form.patchValue({ treatment_plan_id: '' });
  }

  openPlanModal(): void {
    const cond = this.conditionsGroup.value;
    this.planModalPreset.set({
      name: this.form.get('name')?.value || undefined,
      start_date: cond.start_date || undefined,
      estimated_end_date: cond.end_date || undefined,
      total_sessions: cond.num_citas || undefined,
    });
    this.showPlanModal.set(true);
  }

  onPlanCreated(plan: TreatmentPlan): void {
    this.treatmentPlans.update(list => [plan, ...list]);
    this.form.patchValue({ treatment_plan_id: plan.id });
    this.showPlanModal.set(false);
  }

  hasError(f: string): boolean { const c = this.form.get(f); return !!(c?.invalid && c?.touched); }

  onSubmit(): void {
    if (this.form.invalid || !this.selectedPatient()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const val = this.form.value;
    const cond = val.conditions;

    if (this.isEditMode()) {
      const payload: any = {
        name: val.name,
        num_citas: +cond.num_citas,
        start_date: cond.start_date || null,
        end_date: cond.end_date || null,
        notes: val.notes || null,
      };
      // Cost fields are only accepted by the backend while paid_installments == 0 —
      // omit them entirely once locked so editing name/notes/dates/num_citas still works.
      if (!this.costLocked()) {
        payload.calc_mode = cond.calc_mode;
        payload.down_payment = parseFloat(cond.down_payment) || 0;
        if (cond.calc_mode === 'per_cita') {
          payload.cost_per_cita = parseFloat(cond.cost_per_cita) || 0;
        } else {
          payload.total_amount = parseFloat(cond.total_amount) || 0;
        }
      }
      this.billingService.updatePaymentPlan(this.planId!, payload).subscribe({
        next: () => this.router.navigate(['/billing/payment-plans', this.planId]),
        error: err => { this.errorMsg.set(err.error?.error || 'Error al guardar'); this.saving.set(false); },
      });
      return;
    }

    const payload: any = {
      patient_id: this.selectedPatient()!.id,
      treatment_plan_id: +val.treatment_plan_id,
      name: val.name,
      calc_mode: cond.calc_mode,
      num_citas: +cond.num_citas,
      down_payment: parseFloat(cond.down_payment) || 0,
      start_date: cond.start_date || undefined,
      end_date: cond.end_date || undefined,
      notes: val.notes || undefined,
    };
    if (cond.calc_mode === 'per_cita') {
      payload.cost_per_cita = parseFloat(cond.cost_per_cita) || 0;
    } else {
      payload.total_amount = parseFloat(cond.total_amount) || 0;
    }
    this.billingService.createPaymentPlan(payload).subscribe({
      next: res => {
        const planId = res.payment_plan.id;
        if (this.budgetId) {
          this.billingService.linkBudgetPlan(this.budgetId, planId).subscribe({
            next: () => this.router.navigate(['/billing/payment-plans', planId]),
            // The plan was already created successfully — still navigate there even if
            // linking the budget back failed, rather than stranding the user on the form.
            error: () => this.router.navigate(['/billing/payment-plans', planId]),
          });
        } else {
          this.router.navigate(['/billing']);
        }
      },
      error: err => { this.errorMsg.set(err.error?.error || 'Error al crear'); this.saving.set(false); },
    });
  }
}
