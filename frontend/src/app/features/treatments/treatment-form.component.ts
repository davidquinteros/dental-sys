import { Component, EventEmitter, Input, OnInit, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { TreatmentService, PatientService, AppointmentService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, Treatment, Appointment, TreatmentPlan, Medication } from '../../core/models';

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
  /** Pre-fills the associated appointment (cita de referencia) for embedded mode. */
  @Input() presetAppointmentId: number | null = null;
  @Output() saved = new EventEmitter<Treatment>();
  @Output() cancelled = new EventEmitter<void>();

  form: FormGroup;
  medications: FormArray;
  readonly medicationForms = [
    'Comprimido', 'Cápsula', 'Jarabe', 'Gotas', 'Inyectable',
    'Crema/Ungüento', 'Enjuague bucal', 'Otro',
  ];
  readonly durationOptions = [
    '1 día', '2 días', '3 días', '4 días', '5 días', '6 días', '7 días', 'Otro',
  ];
  saving = signal(false);
  errorMsg = signal('');
  isEdit = signal(false);
  editingTreatment = signal<Treatment | null>(null);
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
    this.medications = this.fb.array([]);
    this.form = this.fb.group({
      procedure: ['', Validators.required],
      tooth_number: [''],
      tooth_surface: [''],
      diagnosis: [''],
      description: [''],
      clinical_notes: [''],
      next_steps: [''],
      appointment_id: [''],
      treatment_plan_id: [''],
      has_prescription: [false],
      medications: this.medications,
      prescription_notes: [''],
    });
  }

  private newMedicationGroup(med?: Medication): FormGroup {
    const presetForms = this.medicationForms.slice(0, -1);
    const isOtherForm = !!med?.form && !presetForms.includes(med.form);
    const presetDurations = this.durationOptions.slice(0, -1);
    const isOtherDuration = !!med?.duration && !presetDurations.includes(med.duration);
    return this.fb.group({
      name: [med?.name ?? '', Validators.required],
      concentration: [med?.concentration ?? ''],
      form: [isOtherForm ? 'Otro' : (med?.form ?? '')],
      form_custom: [isOtherForm ? med!.form : ''],
      quantity: [med?.quantity ?? ''],
      dosage: [med?.dosage ?? '', Validators.required],
      duration: [isOtherDuration ? 'Otro' : (med?.duration ?? '')],
      duration_custom: [isOtherDuration ? med!.duration : ''],
      indications: [med?.indications ?? ''],
    });
  }

  addMedication(): void {
    this.medications.push(this.newMedicationGroup());
  }

  removeMedication(i: number): void {
    this.medications.removeAt(i);
  }

  onPrescriptionToggle(): void {
    if (!this.form.get('has_prescription')?.value) {
      while (this.medications.length) this.medications.removeAt(0);
    }
  }

  ngOnInit(): void {
    if (this.embedded) {
      if (this.presetPatient) {
        this.selectedPatient.set(this.presetPatient);
        this.loadPatientLinks(this.presetPatient.id, this.presetAppointmentId, this.presetPlanId);
      }
      return;
    }

    const editId = this.route.snapshot.paramMap.get('id');
    if (editId) {
      this.isEdit.set(true);
      this.treatmentService.getById(+editId).subscribe(res => {
        const t = res.treatment;
        this.editingTreatment.set(t);
        this.form.patchValue({
          procedure: t.procedure,
          tooth_number: t.tooth_number ?? '',
          tooth_surface: t.tooth_surface ?? '',
          diagnosis: t.diagnosis ?? '',
          description: t.description ?? '',
          clinical_notes: t.clinical_notes ?? '',
          next_steps: t.next_steps ?? '',
          has_prescription: t.has_prescription,
          prescription_notes: t.prescription_notes ?? '',
        });
        (t.medications ?? []).forEach(m => this.medications.push(this.newMedicationGroup(m)));
      });
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
      consulta_general: 'Consulta', limpieza_dental: 'Limpieza', extraccion: 'Extracción',
      filling: 'Empaste', endodontics: 'Endodoncia', orthodontics: 'Ortodoncia',
      implant: 'Implante', blanqueamiento: 'Blanqueamiento', corona: 'Corona',
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
    if (this.form.invalid || (!this.isEdit() && !this.selectedPatient())) {
      this.form.markAllAsTouched();
      if (!this.isEdit() && !this.selectedPatient()) this.errorMsg.set('Seleccione un paciente');
      return;
    }
    this.saving.set(true);
    this.errorMsg.set('');
    const val = this.form.value;
    const medications = this.medications.controls.map(c => {
      const g = c.value;
      return {
        name: g.name,
        concentration: g.concentration || null,
        form: g.form === 'Otro' ? (g.form_custom || null) : (g.form || null),
        quantity: g.quantity || null,
        dosage: g.dosage,
        duration: g.duration === 'Otro' ? (g.duration_custom || null) : (g.duration || null),
        indications: g.indications || null,
      };
    });
    const clinicalFields = {
      procedure: val.procedure,
      tooth_number: val.tooth_number || null,
      tooth_surface: val.tooth_surface || null,
      diagnosis: val.diagnosis || null,
      description: val.description || null,
      clinical_notes: val.clinical_notes || null,
      next_steps: val.next_steps || null,
      has_prescription: !!val.has_prescription,
      medications: val.has_prescription ? medications : [],
      prescription_notes: val.has_prescription ? (val.prescription_notes || null) : null,
    };

    if (this.isEdit()) {
      const id = this.editingTreatment()!.id;
      this.treatmentService.update(id, clinicalFields).subscribe({
        next: () => { this.saving.set(false); this.router.navigate(['/treatments', id]); },
        error: err => { this.errorMsg.set(err.error?.error || 'Error al actualizar'); this.saving.set(false); },
      });
      return;
    }

    const payload: any = { ...clinicalFields, patient_id: this.selectedPatient()!.id };
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
