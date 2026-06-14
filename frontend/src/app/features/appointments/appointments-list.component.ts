import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AppointmentService, UserService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Appointment, User } from '../../core/models';

interface AppointmentFilters {
  status: string;
  doctor_id: string;
  date_from: string;
  date_to: string;
  patient_id?: string;
}

@Component({
  selector: 'app-appointments',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './appointments-list.component.html',
  styleUrl: './appointments-list.component.css',
})
export class AppointmentsListComponent implements OnInit {
  appointments = signal<Appointment[]>([]);
  doctors = signal<User[]>([]);
  loading = signal(true);
  currentPage = signal(1);
  totalPages = signal(1);
  total = signal(0);

  filters: AppointmentFilters = { status: '', doctor_id: '', date_from: '', date_to: '' };

  constructor(
    private apptService: AppointmentService,
    private userService: UserService,
    public auth: AuthService,
    private route: ActivatedRoute,
  ) {}

  ngOnInit(): void {
    // Pre-fill patient_id from query params if present
    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) this.filters['patient_id'] = patientId;
    this.userService.getDoctors().subscribe(res => this.doctors.set(res.doctors));
    this.loadAppointments();
  }

  loadAppointments(): void {
    this.loading.set(true);
    const params = { ...this.filters, page: this.currentPage(), per_page: 25 };
    this.apptService.getAll(params).subscribe({
      next: res => {
        this.appointments.set(res.appointments);
        this.total.set(res.total);
        this.totalPages.set(res.pages || 1);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  onFilterChange(): void { this.currentPage.set(1); this.loadAppointments(); }
  clearFilters(): void { this.filters = { status: '', doctor_id: '', date_from: '', date_to: '' }; this.onFilterChange(); }
  goToPage(p: number): void { this.currentPage.set(p); this.loadAppointments(); }

  updateStatus(appt: Appointment, status: string): void {
    this.apptService.update(appt.id, { status: status as any }).subscribe({
      next: res => {
        this.appointments.update(list => list.map(a => a.id === appt.id ? res.appointment : a));
      },
    });
  }

  quickStats() {
    const list = this.appointments();
    const count = (s: string) => list.filter(a => a.status === s).length;
    return [
      { label: 'Programadas', count: count('scheduled'), color: 'blue' },
      { label: 'Confirmadas', count: count('confirmed'), color: 'teal' },
      { label: 'En curso', count: count('in_progress'), color: 'orange' },
      { label: 'Completadas', count: count('completed'), color: 'green' },
      { label: 'Canceladas', count: count('cancelled'), color: 'red' },
    ];
  }

  isPast(appt: Appointment): boolean { return new Date(appt.scheduled_at) < new Date() && appt.status !== 'completed'; }
  formatDate(iso: string): string { return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'short', year: 'numeric' }); }
  formatTime(iso: string): string { return new Date(iso).toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit', hour12: false }); }

  typeLabel(t: string): string {
    const m: Record<string, string> = {
      consultation: 'Consulta', cleaning: 'Limpieza', extraction: 'Extracción',
      filling: 'Empaste', endodontics: 'Endodoncia', orthodontics: 'Ortodoncia',
      implant: 'Implante', whitening: 'Blanqueamiento', crown: 'Corona',
      followup: 'Seguimiento', other: 'Otro',
    };
    return m[t] ?? t;
  }
}
