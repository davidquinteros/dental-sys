import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { PatientService, TreatmentService, UserService } from '../../core/services/api.service';
import { Patient, Appointment, Treatment, TreatmentPlan, User } from '../../core/models';
import { OdontogramComponent } from './odontogram.component';

@Component({
  selector: 'app-patient-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, ReactiveFormsModule, FormsModule, OdontogramComponent],
  templateUrl: './patient-detail.component.html',
  styleUrl: './patient-detail.component.css',
})
export class PatientDetailComponent implements OnInit {
  patient = signal<Patient | null>(null);
  appointments = signal<Appointment[]>([]);
  treatments = signal<Treatment[]>([]);
  plans = signal<TreatmentPlan[]>([]);
  loading = signal(true);
  activeTab = signal('odontogram');

  // Treatment modal
  showTreatmentModal = signal(false);
  treatmentSaving = signal(false);
  treatmentError = signal('');
  treatmentForm: FormGroup;

  // Plan modal (create)
  doctors = signal<User[]>([]);
  showPlanModal = signal(false);
  planSaving = signal(false);
  planError = signal('');
  planForm: FormGroup;

  // Plan detail modal
  showPlanDetailModal = signal(false);
  planDetailLoading = signal(false);
  selectedPlan = signal<TreatmentPlan | null>(null);

  // Notes modal
  showNotesModal = signal(false);
  notesSaving = signal(false);
  notesError = signal('');
  notesValue = '';

  get tabs() {
    return [
      { key: 'odontogram', label: 'Odontograma' },
      { key: 'appointments', label: 'Citas', count: this.appointments().length },
      { key: 'treatments', label: 'Atenciones', count: this.treatments().length },
      { key: 'plans', label: 'Planes de Tratamiento', count: this.plans().length },
      { key: 'notes', label: 'Notas Médicas' },
    ];
  }

  activePlans(): number {
    return this.plans().filter(p => p.status === 'active').length;
  }

  constructor(
    private route: ActivatedRoute,
    private patientService: PatientService,
    private treatmentService: TreatmentService,
    private userService: UserService,
    private fb: FormBuilder,
  ) {
    this.treatmentForm = this.fb.group({
      procedure:         ['', Validators.required],
      tooth_number:      [''],
      tooth_surface:     [''],
      diagnosis:         [''],
      description:       [''],
      clinical_notes:    [''],
      prescriptions:     [''],
      next_steps:        [''],
      appointment_id:    [''],
      treatment_plan_id: [''],
    });

    this.planForm = this.fb.group({
      name:               ['', Validators.required],
      treatment_type:     ['', Validators.required],
      doctor_id:          ['', Validators.required],
      total_sessions:     [''],
      tooth_number:       [''],
      start_date:         [''],
      estimated_end_date: [''],
      description:        [''],
      notes:              [''],
    });
  }

  ngOnInit(): void {
    this.userService.getDoctors().subscribe(res => this.doctors.set(res.doctors));
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.patientService.getHistory(id).subscribe({
      next: res => {
        this.patient.set(res.patient);
        this.appointments.set(res.appointments);
        this.treatments.set(res.treatments);
        this.plans.set(res.treatment_plans);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  initials(p: Patient): string { return `${p.first_name[0]}${p.last_name[0]}`.toUpperCase(); }
  formatDate(iso: string): string { return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'short', year: 'numeric' }); }
  formatDateTime(iso: string): string { return new Date(iso).toLocaleString('es-BO', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }

  typeLabel(t: string): string {
    const m: Record<string, string> = {
      consultation: 'Consulta', cleaning: 'Limpieza', extraction: 'Extracción',
      filling: 'Empaste', endodontics: 'Endodoncia', orthodontics: 'Ortodoncia',
      implant: 'Implante', whitening: 'Blanqueamiento', crown: 'Corona',
      followup: 'Seguimiento', other: 'Otro',
    };
    return m[t] ?? t;
  }

  statusLabel(s: string): string {
    const m: Record<string, string> = {
      scheduled: 'Programada', confirmed: 'Confirmada', in_progress: 'En curso',
      completed: 'Completada', cancelled: 'Cancelada', no_show: 'No asistió',
    };
    return m[s] ?? s;
  }

  planStatusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', on_hold: 'En pausa' };
    return m[s] ?? s;
  }

  // ── Treatment modal ──────────────────────────────────────────────────────────
  openTreatmentModal(): void {
    this.treatmentForm.reset();
    this.treatmentError.set('');
    this.showTreatmentModal.set(true);
  }

  saveTreatment(): void {
    if (this.treatmentForm.invalid) {
      this.treatmentForm.markAllAsTouched();
      return;
    }
    this.treatmentSaving.set(true);
    this.treatmentError.set('');
    const val = this.treatmentForm.value;
    const payload: any = {
      patient_id:    this.patient()!.id,
      procedure:     val.procedure,
      tooth_number:  val.tooth_number || null,
      tooth_surface: val.tooth_surface || null,
      diagnosis:     val.diagnosis || null,
      description:   val.description || null,
      clinical_notes: val.clinical_notes || null,
      prescriptions: val.prescriptions || null,
      next_steps:    val.next_steps || null,
    };
    if (val.appointment_id)   payload.appointment_id   = +val.appointment_id;
    if (val.treatment_plan_id) payload.treatment_plan_id = +val.treatment_plan_id;

    this.treatmentService.create(payload).subscribe({
      next: res => {
        this.treatments.update(list => [res.treatment, ...list]);
        this.showTreatmentModal.set(false);
        this.treatmentSaving.set(false);
        this.activeTab.set('treatments');
      },
      error: err => {
        this.treatmentError.set(err.error?.error || 'Error al registrar la atención');
        this.treatmentSaving.set(false);
      },
    });
  }

  // ── Plan detail modal ─────────────────────────────────────────────────────────
  openPlanDetail(planId: number): void {
    this.selectedPlan.set(null);
    this.planDetailLoading.set(true);
    this.showPlanDetailModal.set(true);
    this.treatmentService.getPlan(planId, true).subscribe({
      next: res => { this.selectedPlan.set(res.treatment_plan); this.planDetailLoading.set(false); },
      error: () => this.planDetailLoading.set(false),
    });
  }

  openTreatmentFromPlan(plan: TreatmentPlan): void {
    this.showPlanDetailModal.set(false);
    this.treatmentForm.reset();
    this.treatmentForm.patchValue({ treatment_plan_id: plan.id });
    this.treatmentError.set('');
    this.showTreatmentModal.set(true);
  }

  // ── Plan modal (create) ───────────────────────────────────────────────────────
  openPlanModal(): void {
    this.planForm.reset();
    this.planError.set('');
    this.showPlanModal.set(true);
  }

  savePlan(): void {
    if (this.planForm.invalid) { this.planForm.markAllAsTouched(); return; }
    this.planSaving.set(true);
    this.planError.set('');
    const val = this.planForm.value;
    const payload: any = {
      patient_id:         this.patient()!.id,
      name:               val.name,
      treatment_type:     val.treatment_type,
      doctor_id:          +val.doctor_id,
      total_sessions:     val.total_sessions ? +val.total_sessions : null,
      tooth_number:       val.tooth_number || null,
      start_date:         val.start_date || null,
      estimated_end_date: val.estimated_end_date || null,
      description:        val.description || null,
      notes:              val.notes || null,
    };
    this.treatmentService.createPlan(payload).subscribe({
      next: res => {
        this.plans.update(list => [res.treatment_plan, ...list]);
        this.showPlanModal.set(false);
        this.planSaving.set(false);
        this.activeTab.set('plans');
      },
      error: err => {
        this.planError.set(err.error?.error || 'Error al crear el plan');
        this.planSaving.set(false);
      },
    });
  }

  // ── Notes modal ───────────────────────────────────────────────────────────────
  openNotesModal(): void {
    this.notesValue = this.patient()!.medical_notes || '';
    this.notesError.set('');
    this.showNotesModal.set(true);
  }

  saveNotes(): void {
    this.notesSaving.set(true);
    this.notesError.set('');
    this.patientService.update(this.patient()!.id, { medical_notes: this.notesValue }).subscribe({
      next: res => {
        this.patient.update(p => p ? { ...p, medical_notes: res.patient.medical_notes } : p);
        this.showNotesModal.set(false);
        this.notesSaving.set(false);
      },
      error: err => {
        this.notesError.set(err.error?.error || 'Error al guardar las notas');
        this.notesSaving.set(false);
      },
    });
  }
}
