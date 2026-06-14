import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { AppointmentService, PatientService, UserService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, User } from '../../core/models';

@Component({
  selector: 'app-appointment-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
  templateUrl: './appointment-form.component.html',
  styleUrl: './appointment-form.component.css',
})
export class AppointmentFormComponent implements OnInit {
  form: FormGroup;
  isEdit = signal(false);
  saving = signal(false);
  errorMsg = signal('');
  doctors = signal<User[]>([]);
  patientResults = signal<Patient[]>([]);
  selectedPatient = signal<Patient | null>(null);
  availabilityChecked = signal(false);
  isAvailable = signal(true);
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
    public auth: AuthService,
  ) {
    this.form = this.fb.group({
      doctor_id: ['', Validators.required],
      scheduled_at: ['', Validators.required],
      duration_minutes: [30],
      appointment_type: ['', Validators.required],
      reason: [''],
      notes: [''],
    });
  }

  ngOnInit(): void {
    this.userService.getDoctors().subscribe(res => this.doctors.set(res.doctors));

    // Pre-fill patient from query
    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => {
        this.selectedPatient.set(res.patient);
      });
    }

    const id = this.route.snapshot.paramMap.get('id');
    if (id && id !== 'new') {
      this.isEdit.set(true);
      this.apptId = +id;
      this.apptService.getById(this.apptId).subscribe({
        next: res => {
          const a = res.appointment;
          this.form.patchValue({
            doctor_id: a.doctor_id,
            scheduled_at: a.scheduled_at.substring(0, 16),
            duration_minutes: a.duration_minutes,
            appointment_type: a.appointment_type,
            reason: a.reason,
            notes: a.notes,
          });
          this.patientService.getById(a.patient_id).subscribe(pr => this.selectedPatient.set(pr.patient));
        },
      });
    }

    // If doctor, prefill own ID
    if (this.auth.isDoctor()) {
      const me = this.auth.currentUser();
      if (me) this.form.patchValue({ doctor_id: me.id });
    }
  }

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

  onDoctorChange(): void { this.checkAvailability(); }
  onDateChange(): void { this.checkAvailability(); }

  checkAvailability(): void {
    const doctorId = this.form.get('doctor_id')?.value;
    const date = this.form.get('scheduled_at')?.value;
    if (!doctorId || !date) { this.availabilityChecked.set(false); return; }
    clearTimeout(this.availabilityTimeout);
    this.availabilityTimeout = setTimeout(() => {
      this.apptService.checkAvailability(+doctorId, date).subscribe({
        next: res => {
          const selectedTime = new Date(date).getTime();
          const duration = this.form.get('duration_minutes')?.value || 30;
          const end = selectedTime + duration * 60000;
          const conflict = res.booked_slots.some((slot: any) => {
            const slotStart = new Date(slot.start).getTime();
            const slotEnd = new Date(slot.end).getTime();
            return !(end <= slotStart || selectedTime >= slotEnd) &&
              (!this.apptId || slot.appointment_id !== this.apptId);
          });
          this.isAvailable.set(!conflict);
          this.availabilityChecked.set(true);
        },
      });
    }, 500);
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
