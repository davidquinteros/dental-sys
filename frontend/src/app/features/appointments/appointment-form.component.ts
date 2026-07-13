import { Component, EventEmitter, Input, OnInit, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import {
  AppointmentService, PatientService, UserService,
  ConsultorioService, AppointmentTypeService, TreatmentService,
} from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Appointment, Patient, User, Consultorio, AppointmentTypeItem, TreatmentPlan } from '../../core/models';
import { CalendarComponent } from '../calendar/calendar.component';
import { ConfirmBackdropCloseDirective } from '../../shared/directives/confirm-backdrop-close.directive';

@Component({
  selector: 'app-appointment-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink, CalendarComponent, ConfirmBackdropCloseDirective],
  templateUrl: './appointment-form.component.html',
  styleUrl: './appointment-form.component.css',
})
export class AppointmentFormComponent implements OnInit {
  /** When true, renders without page chrome (and calendar picker) and emits (saved)/(cancelled) instead of navigating. */
  @Input() embedded = false;
  /** Pre-selected patient for embedded mode (skips the patient search card). */
  @Input() presetPatient: Patient | null = null;
  /** Appointment to edit in embedded mode (omit for creating a new one). */
  @Input() appointmentId: number | null = null;
  @Output() saved = new EventEmitter<Appointment>();
  @Output() cancelled = new EventEmitter<void>();

  form: FormGroup;
  isEdit = signal(false);
  saving = signal(false);
  errorMsg = signal('');

  doctors         = signal<User[]>([]);
  consultorios    = signal<Consultorio[]>([]);
  appointmentTypes = signal<AppointmentTypeItem[]>([]);
  patientPlans    = signal<TreatmentPlan[]>([]);

  patientResults  = signal<Patient[]>([]);
  selectedPatient = signal<Patient | null>(null);

  availabilityChecked = signal(false);
  isAvailable         = signal(true);
  consultorioAvailabilityChecked = signal(false);
  isConsultorioAvailable         = signal(true);

  /** Mirrors the form's current date/duration so the embedded calendar can highlight it. */
  previewSlot = signal<{ start: Date; end: Date } | null>(null);

  // Patient quick-create modal
  showPatientModal   = signal(false);
  patientModalSaving = signal(false);
  patientModalError  = signal('');
  newPatient = { first_name: '', last_name: '', document_number: '', phone: '', gender: 'M', date_of_birth: '' };

  patientSearch = '';
  private searchTimeout: any;
  private availabilityTimeout: any;
  private apptId?: number;

  constructor(
    private fb: FormBuilder,
    private route: ActivatedRoute,
    private router: Router,
    private apptService: AppointmentService,
    private patientService: PatientService,
    private userService: UserService,
    private consultorioService: ConsultorioService,
    private apptTypeService: AppointmentTypeService,
    private treatmentService: TreatmentService,
    public auth: AuthService,
  ) {
    this.form = this.fb.group({
      doctor_id:         ['', Validators.required],
      consultorio_id:    ['', Validators.required],
      scheduled_at:      ['', Validators.required],
      duration_minutes:  [30],
      appointment_type:  ['', Validators.required],
      treatment_plan_id: [''],
      session_number:    [''],
      reason:            [''],
      notes:             [''],
    });
  }

  ngOnInit(): void {
    this.userService.getDoctors().subscribe(res => this.doctors.set(res.doctors));
    this.consultorioService.getAll().subscribe(res => this.consultorios.set(res.consultorios));
    this.apptTypeService.getAll().subscribe(res => this.appointmentTypes.set(res.appointment_types));

    if (this.embedded) {
      if (this.presetPatient) {
        this.selectedPatient.set(this.presetPatient);
        if (!this.appointmentId) {
          this.loadPatientPlans(this.presetPatient.id);
        }
      }
      if (this.appointmentId) {
        this.isEdit.set(true);
        this.apptId = this.appointmentId;
        this.loadAppointment(this.apptId);
      }
      if (this.auth.isDoctor()) {
        const me = this.auth.currentUser();
        if (me) this.form.patchValue({ doctor_id: me.id });
      }
      return;
    }

    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => {
        this.selectedPatient.set(res.patient);
        this.loadPatientPlans(res.patient.id);
      });
    }

    const date = this.route.snapshot.queryParamMap.get('date');
    if (date) {
      this.form.patchValue({ scheduled_at: date.substring(0, 16) });
    }

    const id = this.route.snapshot.paramMap.get('id');
    if (id && id !== 'new') {
      this.isEdit.set(true);
      this.apptId = +id;
      this.loadAppointment(this.apptId, true);
    }

    if (this.auth.isDoctor()) {
      const me = this.auth.currentUser();
      if (me) this.form.patchValue({ doctor_id: me.id });
    }
  }

  private loadAppointment(id: number, fetchPatient = false): void {
    this.apptService.getById(id).subscribe({
      next: res => {
        const a = res.appointment;
        this.form.patchValue({
          doctor_id:         a.doctor_id,
          consultorio_id:    a.consultorio_id ?? '',
          scheduled_at:      a.scheduled_at.substring(0, 16),
          duration_minutes:  a.duration_minutes,
          appointment_type:  a.appointment_type,
          treatment_plan_id: a.treatment_plan_id ?? '',
          session_number:    a.session_number ?? '',
          reason:            a.reason,
          notes:             a.notes,
        });
        if (fetchPatient) {
          this.patientService.getById(a.patient_id).subscribe(pr => {
            this.selectedPatient.set(pr.patient);
            this.loadPatientPlans(pr.patient.id, a.treatment_plan_id);
          });
        } else {
          const patientId = this.selectedPatient()?.id ?? a.patient_id;
          this.loadPatientPlans(patientId, a.treatment_plan_id);
        }
        this.updatePreviewSlot();
      },
    });
  }

  // ── Patient search ───────────────────────────────────────────────────────────

  onPatientSearch(): void {
    clearTimeout(this.searchTimeout);
    if (!this.patientSearch || this.patientSearch.length < 2) {
      this.patientResults.set([]); return;
    }
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
    this.form.patchValue({ treatment_plan_id: '', session_number: '' });
    this.loadPatientPlans(p.id);
  }

  clearPatient(): void {
    this.selectedPatient.set(null);
    this.patientPlans.set([]);
    this.form.patchValue({ treatment_plan_id: '', session_number: '' });
  }

  private loadPatientPlans(patientId: number, includePlanId?: number | null): void {
    this.treatmentService.getPlans({ patient_id: patientId, status: 'active' }).subscribe(res => {
      const plans: TreatmentPlan[] = res.treatment_plans;
      if (includePlanId && !plans.some(p => p.id === includePlanId)) {
        this.treatmentService.getPlan(includePlanId).subscribe(r => {
          this.patientPlans.set([r.treatment_plan, ...plans]);
        });
      } else {
        this.patientPlans.set(plans);
      }
    });
  }

  onPlanChange(): void {
    if (!this.form.get('treatment_plan_id')?.value) {
      this.form.patchValue({ session_number: '' });
    }
  }

  // ── Quick patient create modal ────────────────────────────────────────────────

  openPatientModal(): void {
    this.newPatient = { first_name: '', last_name: '', document_number: '', phone: '', gender: 'M', date_of_birth: '' };
    this.patientModalError.set('');
    this.showPatientModal.set(true);
  }

  saveQuickPatient(): void {
    if (!this.newPatient.first_name.trim() || !this.newPatient.last_name.trim() || !this.newPatient.document_number.trim()) {
      this.patientModalError.set('Nombre, apellido y C.I. son requeridos');
      return;
    }
    this.patientModalSaving.set(true);
    const payload: any = {
      first_name:      this.newPatient.first_name.trim(),
      last_name:       this.newPatient.last_name.trim(),
      document_number: this.newPatient.document_number.trim(),
      phone:           this.newPatient.phone.trim() || undefined,
      gender:          this.newPatient.gender || undefined,
      date_of_birth:   this.newPatient.date_of_birth || undefined,
    };
    this.patientService.create(payload).subscribe({
      next: res => {
        this.selectPatient(res.patient);
        this.showPatientModal.set(false);
        this.patientModalSaving.set(false);
      },
      error: err => {
        this.patientModalError.set(err.error?.error || 'Error al crear el paciente');
        this.patientModalSaving.set(false);
      },
    });
  }

  // ── Availability checks ──────────────────────────────────────────────────────

  onDoctorChange(): void { this.checkAvailability(); }
  onDateChange(): void   { this.checkAvailability(); }
  onConsultorioChange(): void { this.checkConsultorioAvailability(); }

  /** Updates the highlighted slot on the embedded calendar to match the form's current date/duration. */
  updatePreviewSlot(): void {
    const date = this.form.get('scheduled_at')?.value;
    if (!date) { this.previewSlot.set(null); return; }
    const start = new Date(date);
    const duration = this.form.get('duration_minutes')?.value || 30;
    this.previewSlot.set({ start, end: new Date(start.getTime() + duration * 60000) });
  }

  checkAvailability(): void {
    this.updatePreviewSlot();
    const doctorId = this.form.get('doctor_id')?.value;
    const date     = this.form.get('scheduled_at')?.value;
    if (!doctorId || !date) { this.availabilityChecked.set(false); return; }
    clearTimeout(this.availabilityTimeout);
    this.availabilityTimeout = setTimeout(() => {
      const duration     = this.form.get('duration_minutes')?.value || 30;
      const selectedTime = new Date(date).getTime();
      const end          = selectedTime + duration * 60000;
      const INACTIVE     = ['cancelled', 'no_show', 'completed'];

      this.apptService.getAll({
        date_from: date.substring(0, 10) + 'T00:00:00',
        date_to:   date.substring(0, 10) + 'T23:59:59',
        all: true, per_page: 200,
      }).subscribe({
        next: res => {
          const appts: any[] = res.appointments;
          const overlaps = (a: any): boolean => {
            if (this.apptId && a.id === this.apptId) return false;
            if (INACTIVE.includes(a.status)) return false;
            const aStart = new Date(a.scheduled_at).getTime();
            const aEnd   = aStart + a.duration_minutes * 60000;
            return !(end <= aStart || selectedTime >= aEnd);
          };

          this.isAvailable.set(!appts.some(a => a.doctor_id === +doctorId && overlaps(a)));
          this.availabilityChecked.set(true);

          const consultorioId = this.form.get('consultorio_id')?.value;
          if (consultorioId) {
            this.isConsultorioAvailable.set(!appts.some(a => a.consultorio_id === +consultorioId && overlaps(a)));
            this.consultorioAvailabilityChecked.set(true);
          }
        },
      });
    }, 500);
  }

  checkConsultorioAvailability(): void {
    const consultorioId = this.form.get('consultorio_id')?.value;
    const date          = this.form.get('scheduled_at')?.value;
    if (!consultorioId || !date) { this.consultorioAvailabilityChecked.set(false); return; }
    const duration     = this.form.get('duration_minutes')?.value || 30;
    const selectedTime = new Date(date).getTime();
    const end          = selectedTime + duration * 60000;
    const INACTIVE     = ['cancelled', 'no_show', 'completed'];

    this.apptService.getAll({
      date_from: date.substring(0, 10) + 'T00:00:00',
      date_to:   date.substring(0, 10) + 'T23:59:59',
      all: true, per_page: 200,
    }).subscribe({
      next: res => {
        const conflict = (res.appointments as any[]).some(a => {
          if (a.consultorio_id !== +consultorioId) return false;
          if (this.apptId && a.id === this.apptId) return false;
          if (INACTIVE.includes(a.status)) return false;
          const aStart = new Date(a.scheduled_at).getTime();
          const aEnd   = aStart + a.duration_minutes * 60000;
          return !(end <= aStart || selectedTime >= aEnd);
        });
        this.isConsultorioAvailable.set(!conflict);
        this.consultorioAvailabilityChecked.set(true);
      },
    });
  }

  onCalendarDateSelected(isoDate: string): void {
    this.form.patchValue({ scheduled_at: isoDate.substring(0, 16) });
    this.checkAvailability();
  }

  hasError(field: string): boolean {
    const c = this.form.get(field);
    return !!(c?.invalid && c?.touched);
  }

  onSubmit(): void {
    if (this.form.invalid || !this.selectedPatient()) {
      this.form.markAllAsTouched();
      if (!this.selectedPatient()) this.errorMsg.set('Seleccione un paciente');
      return;
    }
    this.saving.set(true);
    this.errorMsg.set('');
    const raw = this.form.value;
    const payload = {
      ...raw,
      patient_id: this.selectedPatient()!.id,
      treatment_plan_id: raw.treatment_plan_id ? +raw.treatment_plan_id : null,
      session_number: raw.session_number ? +raw.session_number : null,
    };
    const req = this.isEdit()
      ? this.apptService.update(this.apptId!, payload)
      : this.apptService.create(payload);
    req.subscribe({
      next: res => {
        if (this.embedded) {
          this.saving.set(false);
          this.saved.emit(res.appointment);
        } else {
          this.router.navigate(['/appointments']);
        }
      },
      error: err => {
        this.errorMsg.set(err.error?.error || 'Error al guardar la cita');
        this.saving.set(false);
      },
    });
  }

  onCancel(): void {
    if (this.embedded) this.cancelled.emit();
  }
}
