import { Component, EventEmitter, Input, OnInit, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { TreatmentService, PatientService, AppointmentService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, Treatment, Appointment, TreatmentPlan } from '../../core/models';

@Component({
  selector: 'app-treatment-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
  templateUrl: './treatment-form.component.html',
  styleUrl: './treatment-form.component.css',
})
export class TreatmentFormComponent implements OnInit {
  /** When true, renders without page chrome and emits (saved)/(cancelled) instead of navigating. */
  @Input() embedded = false;
  /** Pre-selected patient for embedded mode (skips the patient search card). */
  @Input() presetPatient: Patient | null = null;
  /** Pre-fills the associated treatment plan ID for embedded mode. */
  @Input() presetPlanId: number | null = null;
  @Output() saved = new EventEmitter<Treatment>();
  @Output() cancelled = new EventEmitter<void>();

  form: FormGroup;
  saving = signal(false);
  errorMsg = signal('');
  selectedPatient = signal<Patient | null>(null);
  patientResults = signal<Patient[]>([]);
  patientSearch = '';
  private searchTimeout: any;

  appointmentOptions = signal<Appointment[]>([]);
  planOptions = signal<TreatmentPlan[]>([]);
  loadingAppointments = signal(false);
  loadingPlans = signal(false);

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    private patientService: PatientService,
    private appointmentService: AppointmentService,
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
    if (this.embedded) {
      if (this.presetPatient) {
        this.selectedPatient.set(this.presetPatient);
        this.loadPatientLinks(this.presetPatient.id, null, this.presetPlanId);
      }
      return;
    }
    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    const appointmentId = this.route.snapshot.queryParamMap.get('appointment_id');
    const planId = this.route.snapshot.queryParamMap.get('plan_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => {
        this.selectedPatient.set(res.patient);
        this.loadPatientLinks(res.patient.id, appointmentId ? +appointmentId : null, planId ? +planId : null);
      });
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

  selectPatient(p: Patient): void {
    this.selectedPatient.set(p);
    this.patientResults.set([]);
    this.patientSearch = '';
    this.resetLinks();
    this.loadPatientLinks(p.id);
  }

  clearPatient(): void {
    this.selectedPatient.set(null);
    this.resetLinks();
  }

  private resetLinks(): void {
    this.appointmentOptions.set([]);
    this.planOptions.set([]);
    this.form.patchValue({ appointment_id: '', treatment_plan_id: '' });
  }

  /** Loads the patient's appointments for today and active treatment plans, for the "Cita Asociada" / "Plan de Tratamiento" selects. */
  private loadPatientLinks(patientId: number, presetAppointmentId?: number | null, presetPlanId?: number | null): void {
    const { from, to } = this.todayRange();
    this.loadingAppointments.set(true);
    this.appointmentService.getAll({ patient_id: patientId, date_from: from, date_to: to, per_page: 10 }).subscribe(res => {
      const list: Appointment[] = res.appointments;
      if (presetAppointmentId && !list.some(a => a.id === presetAppointmentId)) {
        this.appointmentService.getById(presetAppointmentId).subscribe(r => {
          this.appointmentOptions.set([r.appointment, ...list]);
          this.form.patchValue({ appointment_id: presetAppointmentId });
          this.loadingAppointments.set(false);
        });
      } else {
        this.appointmentOptions.set(list);
        if (presetAppointmentId) this.form.patchValue({ appointment_id: presetAppointmentId });
        this.loadingAppointments.set(false);
      }
    });

    this.loadingPlans.set(true);
    this.treatmentService.getPlans({ patient_id: patientId, status: 'active', per_page: 10 }).subscribe(res => {
      const list: TreatmentPlan[] = res.treatment_plans;
      if (presetPlanId && !list.some(p => p.id === presetPlanId)) {
        this.treatmentService.getPlan(presetPlanId).subscribe(r => {
          this.planOptions.set([r.treatment_plan, ...list]);
          this.form.patchValue({ treatment_plan_id: presetPlanId });
          this.loadingPlans.set(false);
        });
      } else {
        this.planOptions.set(list);
        if (presetPlanId) this.form.patchValue({ treatment_plan_id: presetPlanId });
        this.loadingPlans.set(false);
      }
    });
  }

  private todayRange(): { from: string; to: string } {
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    const day = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    return { from: `${day}T00:00:00`, to: `${day}T23:59:59` };
  }

  appointmentTypeLabel(t: string): string {
    const m: Record<string, string> = {
      consultation: 'Consulta', cleaning: 'Limpieza', extraction: 'Extracción',
      filling: 'Empaste', endodontics: 'Endodoncia', orthodontics: 'Ortodoncia',
      implant: 'Implante', whitening: 'Blanqueamiento', crown: 'Corona',
      followup: 'Seguimiento', other: 'Otro',
    };
    return m[t] ?? t;
  }

  planStatusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', on_hold: 'En pausa' };
    return m[s] ?? s;
  }

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
      next: res => {
        if (this.embedded) {
          this.saving.set(false);
          this.saved.emit(res.treatment);
        } else {
          this.router.navigate(['/treatments', res.treatment.id]);
        }
      },
      error: err => { this.errorMsg.set(err.error?.error || 'Error al registrar'); this.saving.set(false); },
    });
  }

  onCancel(): void {
    if (this.embedded) this.cancelled.emit();
  }
}
