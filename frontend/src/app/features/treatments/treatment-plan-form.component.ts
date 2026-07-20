import { Component, EventEmitter, Input, OnInit, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { TreatmentService, PatientService, UserService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, User, TreatmentPlan } from '../../core/models';
import { TREATMENT_TYPES } from './treatment-type-data';

@Component({
  selector: 'app-treatment-plan-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
  templateUrl: './treatment-plan-form.component.html',
  styleUrl: './treatment-plan-form.component.css',
})
export class TreatmentPlanFormComponent implements OnInit {
  /** When true, renders without page chrome and emits (saved)/(cancelled) instead of navigating. */
  @Input() embedded = false;
  /** Pre-selected patient for embedded mode (skips the patient search field). */
  @Input() presetPatient: Patient | null = null;
  /** Pre-fills matching fields for embedded mode (e.g. inherited from a payment plan already being drafted). */
  @Input() presetValues: { name?: string; start_date?: string; estimated_end_date?: string; total_sessions?: number } | null = null;
  @Output() saved = new EventEmitter<TreatmentPlan>();
  @Output() cancelled = new EventEmitter<void>();

  form: FormGroup;
  saving = signal(false);
  errorMsg = signal('');
  doctors = signal<User[]>([]);
  selectedPatient = signal<Patient | null>(null);
  patientResults = signal<Patient[]>([]);
  patientSearch = '';
  private searchTimeout: any;

  readonly treatmentTypes = TREATMENT_TYPES;

  /** Edit mode is route-driven (treatments/plans/:id/edit) and never combines
   * with `embedded`, which is always a create. */
  isEditMode = signal(false);
  private planId: number | null = null;

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    private patientService: PatientService,
    private userService: UserService,
    public auth: AuthService,
  ) {
    this.form = this.fb.group({
      name: ['', Validators.required],
      treatment_type: ['', Validators.required],
      doctor_id: ['', Validators.required],
      total_sessions: [''],
      tooth_number: [''],
      start_date: [''],
      estimated_end_date: [''],
      description: [''],
      notes: [''],
    });
  }

  ngOnInit(): void {
    // Solo médicos (rol DOCTOR): el médico responsable es una figura clínica, no un
    // admin. El backend valida el mismo conjunto — ver RESPONSIBLE_DOCTOR_ROLES.
    this.userService.getDoctors().subscribe(res => this.doctors.set(res.doctors));
    if (this.embedded) {
      if (this.presetPatient) this.selectedPatient.set(this.presetPatient);
      if (this.presetValues) {
        this.form.patchValue({
          name: this.presetValues.name ?? '',
          start_date: this.presetValues.start_date ?? '',
          estimated_end_date: this.presetValues.estimated_end_date ?? '',
          total_sessions: this.presetValues.total_sessions ?? '',
        });
      }
    } else {
      const idParam = this.route.snapshot.paramMap.get('id');
      if (idParam) {
        this.isEditMode.set(true);
        this.planId = +idParam;
        this.treatmentService.getPlan(this.planId).subscribe(res => {
          const plan = res.treatment_plan;
          this.patientService.getById(plan.patient_id).subscribe(p => this.selectedPatient.set(p.patient));
          this.form.patchValue({
            name: plan.name,
            treatment_type: plan.treatment_type,
            doctor_id: plan.doctor_id,
            total_sessions: plan.total_sessions ?? '',
            tooth_number: plan.tooth_number ?? '',
            start_date: plan.start_date || '',
            estimated_end_date: plan.estimated_end_date || '',
            description: plan.description ?? '',
            notes: plan.notes ?? '',
          });
        });
        // Editing keeps the plan's own doctor — don't fall through to the
        // "default to me" below and silently reassign someone else's plan.
        return;
      }
      const patientId = this.route.snapshot.queryParamMap.get('patient_id');
      if (patientId) {
        this.patientService.getById(+patientId).subscribe(res => this.selectedPatient.set(res.patient));
      }
    }
    if (this.auth.isDoctor()) {
      const me = this.auth.currentUser();
      if (me) this.form.patchValue({ doctor_id: me.id });
    }
  }

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
  hasError(f: string): boolean { const c = this.form.get(f); return !!(c?.invalid && c?.touched); }

  onSubmit(): void {
    if (this.form.invalid || !this.selectedPatient()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const val = this.form.value;
    const payload: any = {
      patient_id: this.selectedPatient()!.id,
      ...val,
      total_sessions: val.total_sessions ? +val.total_sessions : null,
      doctor_id: +val.doctor_id,
    };
    const request = this.isEditMode()
      ? this.treatmentService.updatePlan(this.planId!, payload)
      : this.treatmentService.createPlan(payload);
    request.subscribe({
      next: res => {
        if (this.embedded) {
          this.saving.set(false);
          this.saved.emit(res.treatment_plan);
        } else {
          this.router.navigate(['/treatments/plans', res.treatment_plan.id]);
        }
      },
      error: err => { this.errorMsg.set(err.error?.error || 'Error al guardar'); this.saving.set(false); },
    });
  }

  onCancel(): void {
    if (this.embedded) this.cancelled.emit();
  }
}
