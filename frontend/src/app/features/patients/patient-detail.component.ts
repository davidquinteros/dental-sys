import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { PatientService } from '../../core/services/api.service';
import { Patient, Appointment, Treatment, TreatmentPlan } from '../../core/models';

@Component({
  selector: 'app-patient-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './patient-detail.component.html',
  styleUrl: './patient-detail.component.css',
})
export class PatientDetailComponent implements OnInit {
  patient = signal<Patient | null>(null);
  appointments = signal<Appointment[]>([]);
  treatments = signal<Treatment[]>([]);
  plans = signal<TreatmentPlan[]>([]);
  loading = signal(true);
  activeTab = signal('appointments');

  get tabs() {
    return [
      { key: 'appointments', label: 'Citas', count: this.appointments().length },
      { key: 'treatments', label: 'Atenciones', count: this.treatments().length },
      { key: 'plans', label: 'Planes de Tratamiento', count: this.plans().length },
      { key: 'notes', label: 'Notas Médicas' },
    ];
  }

  activePlans(): number {
    return this.plans().filter(p => p.status === 'active').length;
  }

  constructor(private route: ActivatedRoute, private patientService: PatientService) {}

  ngOnInit(): void {
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
}
