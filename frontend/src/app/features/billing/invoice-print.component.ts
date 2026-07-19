import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { BillingService, PatientService, ClinicService } from '../../core/services/api.service';
import { Invoice, Patient, ClinicInfo } from '../../core/models';
import { formatDate, formatDateLong, formatDateOnly } from '../../core/util/date.util';
import { PrintClinicHeaderComponent } from '../../shared/components/print-clinic-header/print-clinic-header.component';

@Component({
  selector: 'app-invoice-print',
  standalone: true,
  imports: [CommonModule, PrintClinicHeaderComponent],
  templateUrl: './invoice-print.component.html',
  styleUrls: ['../../shared/styles/print-document.css', './invoice-print.component.css'],
})
export class InvoicePrintComponent implements OnInit {
  loading = signal(true);
  error = signal('');
  invoice = signal<Invoice | null>(null);
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
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.billingService.getInvoice(id).subscribe({
      next: res => {
        const invoice = res.invoice;
        this.invoice.set(invoice);
        forkJoin({
          patient: this.patientService.getById(invoice.patient_id),
          clinic: this.clinicService.getInfo(),
        }).subscribe({
          next: ({ patient, clinic }) => {
            this.patient.set(patient.patient);
            this.clinic.set(clinic);
            this.loading.set(false);
          },
          error: () => { this.error.set('No se pudo cargar la información del comprobante'); this.loading.set(false); },
        });
      },
      error: () => { this.error.set('Comprobante no encontrado'); this.loading.set(false); },
    });
  }

  invStatusLabel(s: string): string {
    const m: Record<string, string> = { pending: 'Pendiente', partial: 'Parcial', paid: 'Pagada', cancelled: 'Cancelada', overdue: 'Vencida' };
    return m[s] ?? s;
  }

  formatDate(iso?: string): string { return iso ? formatDate(iso) : '—'; }
  formatDateOnly(iso?: string): string { return iso ? formatDateOnly(iso) : '—'; }

  formatMoney(val?: number | null): string {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
  }

  print(): void {
    window.print();
  }
}
