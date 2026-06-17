import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import {
  AppointmentService, PatientService, UserService,
  ConsultorioService, AppointmentTypeService,
} from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, User, Consultorio, AppointmentTypeItem } from '../../core/models';
import { CalendarComponent } from '../calendar/calendar.component';

@Component({
  selector: 'app-appointment-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink, CalendarComponent],
  templateUrl: './appointment-form.component.html',
  styleUrl: './appointment-form.component.css',
})
export class AppointmentFormComponent implements OnInit {
  form: FormGroup;
  isEdit = signal(false);
  saving = signal(false);
  errorMsg = signal('');

  doctors         = signal<User[]>([]);
  consultorios    = signal<Consultorio[]>([]);
  appointmentTypes = signal<AppointmentTypeItem[]>([]);

  patientResults  = signal<Patient[]>([]);
  selectedPatient = signal<Patient | null>(null);

  availabilityChecked = signal(false);
  isAvailable         = signal(true);
  consultorioAvailabilityChecked = signal(false);
  isConsultorioAvailable         = signal(true);

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
    public auth: AuthService,
  ) {
    this.form = this.fb.group({
      doctor_id:        ['', Validators.required],
      consultorio_id:   ['', Validators.required],
      scheduled_at:     ['', Validators.required],
      duration_minutes: [30],
      appointment_type: ['', Validators.required],
      reason:           [''],
      notes:            [''],
    });
  }

  ngOnInit(): void {
    this.userService.getDoctors().subscribe(res => this.doctors.set(res.doctors));
    this.consultorioService.getAll().subscribe(res => this.consultorios.set(res.consultorios));
    this.apptTypeService.getAll().subscribe(res => this.appointmentTypes.set(res.appointment_types));

    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => this.selectedPatient.set(res.patient));
    }

    const date = this.route.snapshot.queryParamMap.get('date');
    if (date) {
      this.form.patchValue({ scheduled_at: date.substring(0, 16) });
    }

    const id = this.route.snapshot.paramMap.get('id');
    if (id && id !== 'new') {
      this.isEdit.set(true);
      this.apptId = +id;
      this.apptService.getById(this.apptId).subscribe({
        next: res => {
          const a = res.appointment;
          this.form.patchValue({
            doctor_id:        a.doctor_id,
            consultorio_id:   a.consultorio_id ?? '',
            scheduled_at:     a.scheduled_at.substring(0, 16),
            duration_minutes: a.duration_minutes,
            appointment_type: a.appointment_type,
            reason:           a.reason,
            notes:            a.notes,
          });
          this.patientService.getById(a.patient_id).subscribe(pr => this.selectedPatient.set(pr.patient));
        },
      });
    }

    if (this.auth.isDoctor()) {
      const me = this.auth.currentUser();
      if (me) this.form.patchValue({ doctor_id: me.id });
    }
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
  }

  clearPatient(): void { this.selectedPatient.set(null); }

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

  checkAvailability(): void {
    const doctorId = this.form.get('doctor_id')?.value;
    const date     = this.form.get('scheduled_at')?.value;
    if (!doctorId || !date) { this.availabilityChecked.set(false); return; }
    clearTimeout(this.availabilityTimeout);
    this.availabilityTimeout = setTimeout(() => {
      this.apptService.checkAvailability(+doctorId, date).subscribe({
        next: res => {
          const selectedTime = new Date(date).getTime();
          const duration     = this.form.get('duration_minutes')?.value || 30;
          const end          = selectedTime + duration * 60000;
          const conflict     = res.booked_slots.some((slot: any) => {
            const slotStart = new Date(slot.start).getTime();
            const slotEnd   = new Date(slot.end).getTime();
            return !(end <= slotStart || selectedTime >= slotEnd) &&
              (!this.apptId || slot.appointment_id !== this.apptId);
          });
          this.isAvailable.set(!conflict);
          this.availabilityChecked.set(true);
        },
      });
      this.checkConsultorioAvailability();
    }, 500);
  }

  checkConsultorioAvailability(): void {
    const consultorioId = this.form.get('consultorio_id')?.value;
    const date          = this.form.get('scheduled_at')?.value;
    if (!consultorioId || !date) { this.consultorioAvailabilityChecked.set(false); return; }
    const duration     = this.form.get('duration_minutes')?.value || 30;
    const selectedTime = new Date(date).getTime();
    const end          = selectedTime + duration * 60000;

    this.apptService.getAll({
      date_from: date.substring(0, 10) + 'T00:00:00',
      date_to:   date.substring(0, 10) + 'T23:59:59',
      all: true, per_page: 200,
    }).subscribe({
      next: res => {
        const conflict = res.appointments.some((a: any) => {
          if (a.consultorio_id !== +consultorioId) return false;
          if (this.apptId && a.id === this.apptId) return false;
          if (a.status === 'cancelled' || a.status === 'no_show') return false;
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
    const payload = { ...this.form.value, patient_id: this.selectedPatient()!.id };
    const req = this.isEdit()
      ? this.apptService.update(this.apptId!, payload)
      : this.apptService.create(payload);
    req.subscribe({
      next: () => this.router.navigate(['/appointments']),
      error: err => {
        this.errorMsg.set(err.error?.error || 'Error al guardar la cita');
        this.saving.set(false);
      },
    });
  }
}
