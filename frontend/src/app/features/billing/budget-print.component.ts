import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { BillingService, PatientService, ClinicService } from '../../core/services/api.service';
import { Budget, Patient, ClinicInfo } from '../../core/models';
import { formatDateLong, formatDateOnly } from '../../core/util/date.util';
import { PrintClinicHeaderComponent } from '../../shared/components/print-clinic-header/print-clinic-header.component';

@Component({
  selector: 'app-budget-print',
  standalone: true,
  imports: [CommonModule, PrintClinicHeaderComponent],
  templateUrl: './budget-print.component.html',
  styleUrls: ['../../shared/styles/print-document.css', './budget-print.component.css'],
})
export class BudgetPrintComponent implements OnInit {
  loading = signal(true);
  error = signal('');
  budget = signal<Budget | null>(null);
  patient = signal<Patient | null>(null);
  clinic = signal<ClinicInfo | null>(null);
  citasRows = signal<{ label: string; amount: number }[]>([]);

  readonly issuedDate = formatDateLong(new Date().toISOString());

  constructor(
    private route: ActivatedRoute,
    private billingService: BillingService,
    private patientService: PatientService,
    private clinicService: ClinicService,
  ) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.billingService.getBudget(id).subscribe({
      next: res => {
        const budget = res.budget;
        this.budget.set(budget);
        this.buildCitasRows(budget);
        forkJoin({
          patient: this.patientService.getById(budget.patient_id),
          clinic: this.clinicService.getInfo(),
        }).subscribe({
          next: ({ patient, clinic }) => {
            this.patient.set(patient.patient);
            this.clinic.set(clinic);
            this.loading.set(false);
          },
          error: () => { this.error.set('No se pudo cargar la información del presupuesto'); this.loading.set(false); },
        });
      },
      error: () => { this.error.set('Presupuesto no encontrado'); this.loading.set(false); },
    });
  }

  private buildCitasRows(b: Budget): void {
    const rows: { label: string; amount: number }[] = [];
    if (b.down_payment > 0) {
      rows.push({ label: 'Cuota inicial', amount: b.down_payment });
    }
    for (let i = 1; i <= b.num_citas; i++) {
      rows.push({ label: `Cita ${i}`, amount: b.cost_per_cita });
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
