import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { BillingService, PatientService, ClinicService } from '../../core/services/api.service';
import { PaymentPlan, PaymentPlanInstallment, Patient, ClinicInfo } from '../../core/models';
import { formatDate, formatDateLong } from '../../core/util/date.util';
import { PrintClinicHeaderComponent } from '../../shared/components/print-clinic-header/print-clinic-header.component';

@Component({
  selector: 'app-payment-receipt-print',
  standalone: true,
  imports: [CommonModule, PrintClinicHeaderComponent],
  templateUrl: './payment-receipt-print.component.html',
  styleUrls: ['../../shared/styles/print-document.css', './payment-receipt-print.component.css'],
})
export class PaymentReceiptPrintComponent implements OnInit {
  loading = signal(true);
  error = signal('');
  plan = signal<PaymentPlan | null>(null);
  installment = signal<PaymentPlanInstallment | null>(null);
  patient = signal<Patient | null>(null);
  clinic = signal<ClinicInfo | null>(null);

  readonly issuedDate = formatDateLong(new Date().toISOString());

  constructor(
    private route: ActivatedRoute,
    private billingService: BillingService,
    private patientService: PatientService,
    private clinicService: ClinicService,
  ) {}

  ngOnInit(): void {
    const planId = +this.route.snapshot.paramMap.get('id')!;
    const installmentId = +this.route.snapshot.paramMap.get('installmentId')!;

    forkJoin({
      plan: this.billingService.getPaymentPlan(planId),
      installments: this.billingService.getPlanInstallments(planId),
      clinic: this.clinicService.getInfo(),
    }).subscribe({
      next: ({ plan, installments, clinic }) => {
        const p = plan.payment_plan;
        const inst = installments.installments.find(i => i.id === installmentId);
        if (!inst) {
          this.error.set('Comprobante de pago no encontrado');
          this.loading.set(false);
          return;
        }
        this.plan.set(p);
        this.installment.set(inst);
        this.clinic.set(clinic);
        this.patientService.getById(p.patient_id).subscribe({
          next: pat => { this.patient.set(pat.patient); this.loading.set(false); },
          error: () => { this.error.set('No se pudo cargar la información del paciente'); this.loading.set(false); },
        });
      },
      error: () => { this.error.set('No se pudo cargar el comprobante'); this.loading.set(false); },
    });
  }

  // Snapshot as of this payment (see backend total_paid_after/balance_after). Falls back
  // to the plan's live values only for legacy rows the migration couldn't backfill.
  totalPaidAtPayment(): number {
    const inst = this.installment();
    if (inst?.total_paid_after != null) return inst.total_paid_after;
    return this.plan()?.total_paid ?? 0;
  }

  balanceAtPayment(): number {
    const inst = this.installment();
    if (inst?.balance_after != null) return inst.balance_after;
    return this.plan()?.balance ?? 0;
  }

  planTotalAtPayment(): number {
    const inst = this.installment();
    if (inst?.total_paid_after != null && inst?.balance_after != null) {
      return inst.total_paid_after + inst.balance_after;
    }
    return this.plan()?.total_amount ?? 0;
  }

  formatDate(iso?: string): string { return iso ? formatDate(iso) : '—'; }

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  print(): void {
    window.print();
  }
}
