import { Component, EventEmitter, Input, OnInit, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { TreatmentService, PatientService, UserService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, User, TreatmentPlan } from '../../core/models';

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
    this.userService.getDoctors().subscribe(res => this.doctors.set(res.doctors));
    if (this.embedded) {
      if (this.presetPatient) this.selectedPatient.set(this.presetPatient);
    } else {
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
    this.treatmentService.createPlan(payload).subscribe({
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
