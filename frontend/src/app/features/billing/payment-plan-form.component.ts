import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { BillingService, PatientService, TreatmentService } from '../../core/services/api.service';
import { Patient, TreatmentPlan } from '../../core/models';

@Component({
  selector: 'app-payment-plan-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
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
  private planId: number | null = null;

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
      total_amount: ['', [Validators.required, Validators.min(1)]],
      down_payment: [0],
      installments: [3, Validators.required],
      start_date: [''],
      notes: [''],
    });
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
        this.patientService.getById(plan.patient_id).subscribe(pres => this.selectedPatient.set(pres.patient));
        this.form.patchValue({
          name: plan.name,
          treatment_plan_id: plan.treatment_plan_id,
          total_amount: plan.total_amount,
          down_payment: plan.down_payment,
          installments: plan.installments,
          start_date: plan.start_date,
          notes: plan.notes,
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

  recalc(): void { /* computed via getters */ }

  financeAmount(): number {
    const total = parseFloat(this.form.get('total_amount')?.value) || 0;
    const down = parseFloat(this.form.get('down_payment')?.value) || 0;
    return Math.max(0, total - down);
  }

  installmentAmount(): number {
    const installments = parseInt(this.form.get('installments')?.value) || 1;
    return installments > 0 ? this.financeAmount() / installments : 0;
  }

  hasError(f: string): boolean { const c = this.form.get(f); return !!(c?.invalid && c?.touched); }

  formatMoney(val: number): string {
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val || 0);
  }

  onSubmit(): void {
    if (this.form.invalid || !this.selectedPatient()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const val = this.form.value;

    if (this.isEditMode()) {
      const payload = {
        name: val.name,
        total_amount: parseFloat(val.total_amount),
        down_payment: parseFloat(val.down_payment) || 0,
        installments: +val.installments,
        start_date: val.start_date || null,
        notes: val.notes || null,
      };
      this.billingService.updatePaymentPlan(this.planId!, payload).subscribe({
        next: () => this.router.navigate(['/billing/payment-plans', this.planId]),
        error: err => { this.errorMsg.set(err.error?.error || 'Error al guardar'); this.saving.set(false); },
      });
      return;
    }

    const payload = {
      patient_id: this.selectedPatient()!.id,
      treatment_plan_id: +val.treatment_plan_id,
      name: val.name,
      total_amount: parseFloat(val.total_amount),
      down_payment: parseFloat(val.down_payment) || 0,
      installments: +val.installments,
      start_date: val.start_date || undefined,
      notes: val.notes || undefined,
    };
    this.billingService.createPaymentPlan(payload).subscribe({
      next: () => this.router.navigate(['/billing']),
      error: err => { this.errorMsg.set(err.error?.error || 'Error al crear'); this.saving.set(false); },
    });
  }
}
