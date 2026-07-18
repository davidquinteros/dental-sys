import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { PatientService, TreatmentService, AppointmentService, BillingService } from '../../core/services/api.service';
import { Patient, Appointment, Treatment, TreatmentPlan, Invoice, PaymentPlan, Budget } from '../../core/models';
import { formatDate as fmtDate, formatDateTime as fmtDateTime, formatDateOnly as fmtDateOnly } from '../../core/util/date.util';
import { OdontogramComponent } from './odontogram.component';
import { TreatmentFormComponent } from '../treatments/treatment-form.component';
import { TreatmentPlanFormComponent } from '../treatments/treatment-plan-form.component';
import { TreatmentDetailComponent } from '../treatments/treatment-detail.component';
import { MedicalHistoryComponent } from './medical-history.component';
import { AppointmentFormComponent } from '../appointments/appointment-form.component';
import { ConfirmBackdropCloseDirective } from '../../shared/directives/confirm-backdrop-close.directive';
import { treatmentTypeLabel } from '../treatments/treatment-type-data';

@Component({
  selector: 'app-patient-detail',
  standalone: true,
  imports: [
    CommonModule, RouterLink, OdontogramComponent,
    TreatmentFormComponent, TreatmentPlanFormComponent, TreatmentDetailComponent, MedicalHistoryComponent,
    AppointmentFormComponent, ConfirmBackdropCloseDirective,
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

  // Billing tab (Pagos y Presupuestos)
  invoices = signal<Invoice[]>([]);
  paymentPlans = signal<PaymentPlan[]>([]);
  budgets = signal<Budget[]>([]);
  loadingInvoices = signal(true);
  loadingPaymentPlans = signal(true);
  loadingBudgets = signal(true);
  billingSubView = signal<'invoices' | 'plans' | 'budgets'>('invoices');

  // Treatment modal (form delegated to <app-treatment-form embedded>)
  showTreatmentModal = signal(false);
  treatmentPlanPreset = signal<number | null>(null);
  treatmentAppointmentPreset = signal<number | null>(null);

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
      { key: 'billing', label: 'Pagos y Presupuestos' },
      { key: 'notes', label: 'Historia Médica' },
    ];
  }

  /** Payment plan billing a given treatment plan, if one was created for it — used to
   * route the Citas tab's "Registrar pago" action to the plan instead of a one-off invoice. */
  paymentPlanForTreatmentPlan(treatmentPlanId: number): PaymentPlan | undefined {
    return this.paymentPlans().find(p => p.treatment_plan_id === treatmentPlanId);
  }

  activePlans(): number {
    return this.plans().filter(p => p.status === 'active').length;
  }

  constructor(
    private route: ActivatedRoute,
    private patientService: PatientService,
    private treatmentService: TreatmentService,
    private apptService: AppointmentService,
    private billingService: BillingService,
  ) {}

  ngOnInit(): void {
    const tab = this.route.snapshot.queryParamMap.get('tab');
    if (tab) this.activeTab.set(tab);

    const planId = this.route.snapshot.queryParamMap.get('planId');
    if (planId) this.openPlanDetail(+planId);

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

    this.loadBillingData(id);
  }

  // ── Billing tab (Pagos y Presupuestos) ──────────────────────────────────────
  loadBillingData(patientId: number): void {
    this.billingService.getInvoices({ patient_id: patientId, per_page: 100 }).subscribe({
      next: res => { this.invoices.set(res.invoices); this.loadingInvoices.set(false); },
      error: () => this.loadingInvoices.set(false),
    });
    this.billingService.getPaymentPlans({ patient_id: patientId, per_page: 100 }).subscribe({
      next: res => { this.paymentPlans.set(res.payment_plans); this.loadingPaymentPlans.set(false); },
      error: () => this.loadingPaymentPlans.set(false),
    });
    this.billingService.getBudgets({ patient_id: patientId, per_page: 100 }).subscribe({
      next: res => { this.budgets.set(res.budgets); this.loadingBudgets.set(false); },
      error: () => this.loadingBudgets.set(false),
    });
  }

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  invStatusLabel(s: string): string {
    const m: Record<string, string> = { pending: 'Pendiente', partial: 'Parcial', paid: 'Pagada', cancelled: 'Cancelada', overdue: 'Vencida' };
    return m[s] ?? s;
  }

  paymentPlanStatusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', defaulted: 'En mora' };
    return m[s] ?? s;
  }

  budgetStatusLabel(s: string): string {
    const m: Record<string, string> = { draft: 'Borrador', accepted: 'Aceptado', rejected: 'Rechazado' };
    return m[s] ?? s;
  }

  initials(p: Patient): string { return `${p.first_name[0]}${p.last_name[0]}`.toUpperCase(); }
  formatDate(iso: string): string { return fmtDate(iso); }
  formatDateTime(iso: string): string { return fmtDateTime(iso); }

  printMedicalHistory(): void {
    window.open(`/patients/${this.patient()!.id}/historia/imprimir`, '_blank');
  }
  formatDateOnly(iso?: string): string { return iso ? fmtDateOnly(iso) : '—'; }

  /** APPOINTMENT types — a per-clinic catalog in the DB (AppointmentTypeCatalog).
   * Deliberately NOT the treatment-type vocabulary; see treatmentTypeLabel below. */
  typeLabel(t: string): string {
    const m: Record<string, string> = {
      consulta_general: 'Consulta', limpieza_dental: 'Limpieza', extraccion: 'Extracción',
      filling: 'Empaste', endodontics: 'Endodoncia', orthodontics: 'Ortodoncia',
      implant: 'Implante', blanqueamiento: 'Blanqueamiento', corona: 'Corona',
      followup: 'Seguimiento', other: 'Otro',
    };
    return m[t] ?? t;
  }

  /** TREATMENT PLAN types (the shared vocabulary, incl. "Atención General"). */
  treatmentTypeLabel(t?: string): string { return treatmentTypeLabel(t); }

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
    this.treatmentAppointmentPreset.set(null);
    this.showTreatmentModal.set(true);
  }

  /** "Registrar atención" action from the Citas tab — inherits the appointment as the
   * cita de referencia and its treatment plan (if any) so the atención comes pre-linked. */
  openTreatmentFromAppointment(appt: Appointment): void {
    this.treatmentPlanPreset.set(appt.treatment_plan_id ?? null);
    this.treatmentAppointmentPreset.set(appt.id);
    this.showTreatmentModal.set(true);
  }

  onTreatmentSaved(treatment: Treatment): void {
    this.treatments.update(list => [treatment, ...list]);
    this.showTreatmentModal.set(false);
    this.activeTab.set('treatments');

    // Once the atención is registered against a cita still scheduled/confirmed, move it
    // to "en curso" — it no longer makes sense to leave it as merely programmed/confirmed.
    if (treatment.appointment_id) {
      const appt = this.appointments().find(a => a.id === treatment.appointment_id);
      if (appt && (appt.status === 'scheduled' || appt.status === 'confirmed')) {
        this.apptService.update(appt.id, { status: 'in_progress' as any }).subscribe({
          next: res => this.appointments.update(list => list.map(a => a.id === appt.id ? res.appointment : a)),
        });
      }
    }
  }

  openTreatmentDetail(treatmentId: number): void {
    this.selectedTreatmentId.set(treatmentId);
    this.showTreatmentDetailModal.set(true);
  }

  printReceta(treatmentId: number): void {
    window.open(`/treatments/${treatmentId}/receta`, '_blank');
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
