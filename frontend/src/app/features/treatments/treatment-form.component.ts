import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { TreatmentService, PatientService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient } from '../../core/models';

@Component({
  selector: 'app-treatment-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
  templateUrl: './treatment-form.component.html',
  styleUrl: './treatment-form.component.css',
})
export class TreatmentFormComponent implements OnInit {
  form: FormGroup;
  saving = signal(false);
  errorMsg = signal('');
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
    public auth: AuthService,
  ) {
    this.form = this.fb.group({
      procedure: ['', Validators.required],
      tooth_number: [''],
      tooth_surface: [''],
      diagnosis: [''],
      description: [''],
      clinical_notes: [''],
      prescriptions: [''],
      next_steps: [''],
      appointment_id: [''],
      treatment_plan_id: [''],
    });
  }

  ngOnInit(): void {
    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => this.selectedPatient.set(res.patient));
    }
    const appointmentId = this.route.snapshot.queryParamMap.get('appointment_id');
    if (appointmentId) this.form.patchValue({ appointment_id: +appointmentId });
    const planId = this.route.snapshot.queryParamMap.get('plan_id');
    if (planId) this.form.patchValue({ treatment_plan_id: +planId });
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
    if (this.form.invalid || !this.selectedPatient()) {
      this.form.markAllAsTouched();
      if (!this.selectedPatient()) this.errorMsg.set('Seleccione un paciente');
      return;
    }
    this.saving.set(true);
    this.errorMsg.set('');
    const val = this.form.value;
    const payload: any = {
      patient_id: this.selectedPatient()!.id,
      procedure: val.procedure,
      tooth_number: val.tooth_number || null,
      tooth_surface: val.tooth_surface || null,
      diagnosis: val.diagnosis || null,
      description: val.description || null,
      clinical_notes: val.clinical_notes || null,
      prescriptions: val.prescriptions || null,
      next_steps: val.next_steps || null,
    };
    if (val.appointment_id) payload.appointment_id = +val.appointment_id;
    if (val.treatment_plan_id) payload.treatment_plan_id = +val.treatment_plan_id;

    this.treatmentService.create(payload).subscribe({
      next: res => this.router.navigate(['/treatments', res.treatment.id]),
      error: err => { this.errorMsg.set(err.error?.error || 'Error al registrar'); this.saving.set(false); },
    });
  }
}
