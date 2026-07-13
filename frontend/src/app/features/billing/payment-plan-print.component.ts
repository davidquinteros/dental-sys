import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { BillingService, PatientService, ClinicService } from '../../core/services/api.service';
import { PaymentPlan, Patient, ClinicInfo } from '../../core/models';
import { formatDateLong, formatDateOnly } from '../../core/util/date.util';
import { PrintClinicHeaderComponent } from '../../shared/components/print-clinic-header/print-clinic-header.component';

@Component({
  selector: 'app-payment-plan-print',
  standalone: true,
  imports: [CommonModule, PrintClinicHeaderComponent],
  templateUrl: './payment-plan-print.component.html',
  styleUrls: ['../../shared/styles/print-document.css', './payment-plan-print.component.css'],
})
export class PaymentPlanPrintComponent implements OnInit {
  loading = signal(true);
  error = signal('');
  plan = signal<PaymentPlan | null>(null);
  patient = signal<Patient | null>(null);
  clinic = signal<ClinicInfo | null>(null);
  citasRows = signal<{ label: string; amount: number; status: 'paid' | 'partial' | 'pending'; paidAmount?: number }[]>([]);

  readonly issuedDate = formatDateLong(new Date().toISOString());

  constructor(
    private route: ActivatedRoute,
    private billingService: BillingService,
    private patientService: PatientService,
    private clinicService: ClinicService,
  ) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.billingService.getPaymentPlan(id).subscribe({
      next: res => {
        const plan = res.payment_plan;
        this.plan.set(plan);
        this.buildCitasRows(plan);
        forkJoin({
          patient: this.patientService.getById(plan.patient_id),
          clinic: this.clinicService.getInfo(),
        }).subscribe({
          next: ({ patient, clinic }) => {
            this.patient.set(patient.patient);
            this.clinic.set(clinic);
            this.loading.set(false);
          },
          error: () => { this.error.set('No se pudo cargar la información del plan'); this.loading.set(false); },
        });
      },
      error: () => { this.error.set('Plan de pago no encontrado'); this.loading.set(false); },
    });
  }

  private buildCitasRows(p: PaymentPlan): void {
    const rows: { label: string; amount: number; status: 'paid' | 'partial' | 'pending'; paidAmount?: number }[] = [];
    if (p.down_payment > 0) {
      // Enganche is collected like any other payment (see payment-plan-detail); derive
      // its state from total_paid vs down_payment instead of assuming it's pre-paid.
      if (p.total_paid >= p.down_payment) {
        rows.push({ label: 'Cuota inicial', amount: p.down_payment, status: 'paid' });
      } else if (p.total_paid > 0) {
        rows.push({ label: 'Cuota inicial', amount: p.down_payment, status: 'partial', paidAmount: p.total_paid });
      } else {
        rows.push({ label: 'Cuota inicial', amount: p.down_payment, status: 'pending' });
      }
    }
    for (let i = 1; i <= p.installments; i++) {
      if (i <= p.paid_installments) {
        rows.push({ label: `Cita ${i}`, amount: p.installment_amount, status: 'paid' });
      } else if (i === p.paid_installments + 1 && p.partial_progress_amount > 0) {
        rows.push({ label: `Cita ${i}`, amount: p.installment_amount, status: 'partial', paidAmount: p.partial_progress_amount });
      } else {
        rows.push({ label: `Cita ${i}`, amount: p.installment_amount, status: 'pending' });
      }
    }
    this.citasRows.set(rows);
  }

  formatDateOnly(iso?: string): string { return iso ? formatDateOnly(iso) : '—'; }

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  print(): void {
    window.print();
  }
}
