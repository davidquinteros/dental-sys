import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { PatientService, TreatmentService, AppointmentService } from '../../core/services/api.service';
import { Patient, Appointment, Treatment, TreatmentPlan } from '../../core/models';
import { OdontogramComponent } from './odontogram.component';
import { TreatmentFormComponent } from '../treatments/treatment-form.component';
import { TreatmentPlanFormComponent } from '../treatments/treatment-plan-form.component';
import { TreatmentDetailComponent } from '../treatments/treatment-detail.component';
import { MedicalHistoryComponent } from './medical-history.component';
import { AppointmentFormComponent } from '../appointments/appointment-form.component';

@Component({
  selector: 'app-patient-detail',
  standalone: true,
  imports: [
    CommonModule, RouterLink, OdontogramComponent,
    TreatmentFormComponent, TreatmentPlanFormComponent, TreatmentDetailComponent, MedicalHistoryComponent,
    AppointmentFormComponent,
  ],
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

  // Treatment modal (form delegated to <app-treatment-form embedded>)
  showTreatmentModal = signal(false);
  treatmentPlanPreset = signal<number | null>(null);

  // Plan modal (form delegated to <app-treatment-plan-form embedded>)
  showPlanModal = signal(false);

  // Plan detail modal
  showPlanDetailModal = signal(false);
  planDetailLoading = signal(false);
  selectedPlan = signal<TreatmentPlan | null>(null);

  // Treatment detail modal (form delegated to <app-treatment-detail embedded>)
  showTreatmentDetailModal = signal(false);
  selectedTreatmentId = signal<number | null>(null);

  // Appointment edit modal (form delegated to <app-appointment-form embedded>)
  showAppointmentModal = signal(false);
  selectedAppointmentId = signal<number | null>(null);

  get tabs() {
    return [
      { key: 'odontogram', label: 'Odontograma' },
      { key: 'appointments', label: 'Citas', count: this.appointments().length },
      { key: 'treatments', label: 'Atenciones', count: this.treatments().length },
      { key: 'plans', label: 'Planes de Tratamiento', count: this.plans().length },
      { key: 'notes', label: 'Historia Médica' },
    ];
  }

  activePlans(): number {
    return this.plans().filter(p => p.status === 'active').length;
  }

  constructor(
    private route: ActivatedRoute,
    private patientService: PatientService,
    private treatmentService: TreatmentService,
    private apptService: AppointmentService,
  ) {}

  ngOnInit(): void {
    const tab = this.route.snapshot.queryParamMap.get('tab');
    if (tab) this.activeTab.set(tab);

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
    this.treatmentPlanPreset.set(null);
    this.showTreatmentModal.set(true);
  }

  onTreatmentSaved(treatment: Treatment): void {
    this.treatments.update(list => [treatment, ...list]);
    this.showTreatmentModal.set(false);
    this.activeTab.set('treatments');
  }

  openTreatmentDetail(treatmentId: number): void {
    this.selectedTreatmentId.set(treatmentId);
    this.showTreatmentDetailModal.set(true);
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
    this.treatmentPlanPreset.set(plan.id);
    this.showTreatmentModal.set(true);
  }

  // ── Plan modal (create) ───────────────────────────────────────────────────────
  openPlanModal(): void {
    this.showPlanModal.set(true);
  }

  onPlanSaved(plan: TreatmentPlan): void {
    this.plans.update(list => [plan, ...list]);
    this.showPlanModal.set(false);
    this.activeTab.set('plans');
  }

  // ── Appointment status + edit modal ───────────────────────────────────────────
  updateAppointmentStatus(appt: Appointment, status: string): void {
    this.apptService.update(appt.id, { status: status as any }).subscribe({
      next: res => {
        this.appointments.update(list => list.map(a => a.id === appt.id ? res.appointment : a));
      },
    });
  }

  openAppointmentEdit(appt: Appointment): void {
    this.selectedAppointmentId.set(appt.id);
    this.showAppointmentModal.set(true);
  }

  onAppointmentSaved(appt: Appointment): void {
    this.appointments.update(list => list.map(a => a.id === appt.id ? appt : a));
    this.showAppointmentModal.set(false);
  }
}
