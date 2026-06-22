import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { DashboardService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { DashboardData, Appointment } from '../../core/models';
import { CalendarComponent } from '../calendar/calendar.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, CalendarComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  loading = signal(true);
  data = signal<DashboardData | null>(null);

  constructor(
    private dashboardService: DashboardService,
    public auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.dashboardService.getData().subscribe({
      next: d => { this.data.set(d); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  greeting = computed(() => {
    const h = new Date().getHours();
    if (h < 12) return 'Buenos días';
    if (h < 19) return 'Buenas tardes';
    return 'Buenas noches';
  });

  statusBreakdown = computed(() => {
    const d = this.data();
    if (!d) return [];
    const labels: Record<string, string> = {
      scheduled: 'Programadas', confirmed: 'Confirmadas',
      in_progress: 'En curso', completed: 'Completadas',
      cancelled: 'Canceladas', no_show: 'No asistió',
    };
    return Object.entries(d.appointment_status_breakdown)
      .map(([key, count]) => ({ key, count, label: labels[key] ?? key }))
      .filter(i => i.count > 0)
      .sort((a, b) => b.count - a.count);
  });

  upcomingAppointments = computed(() => {
    const d = this.data();
    if (!d) return [];
    const today = new Date();
    today.setHours(23, 59, 59);
    return d.calendar_appointments
      .filter(a => new Date(a.scheduled_at) > today)
      .slice(0, 6);
  });

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '—';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(val);
  }

  formatTime(iso: string): string {
    return new Date(iso).toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit', hour12: false });
  }

  formatDay(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: 'numeric' });
  }

  formatMonth(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { month: 'short' });
  }

  appointmentTypeLabel(type: string): string {
    const labels: Record<string, string> = {
      consulta_general: 'Consulta general', limpieza_dental: 'Limpieza dental',
      extraccion: 'Extracción', filling: 'Empaste',
      endodontics: 'Endodoncia', orthodontics: 'Ortodoncia',
      implant: 'Implante', blanqueamiento: 'Blanqueamiento',
      corona: 'Corona', followup: 'Seguimiento', other: 'Otro',
    };
    return labels[type] ?? type;
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      scheduled: 'Programada', confirmed: 'Confirmada',
      in_progress: 'En curso', completed: 'Completada',
      cancelled: 'Cancelada', no_show: 'No asistió',
    };
    return labels[status] ?? status;
  }
}
