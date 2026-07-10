import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { PatientService, TreatmentService, ClinicService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Patient, Treatment, ClinicInfo } from '../../core/models';
import { ToothData } from './odontogram-data';
import { formatDateLong } from '../../core/util/date.util';
import { PrintClinicHeaderComponent } from '../../shared/components/print-clinic-header/print-clinic-header.component';
import { MedicalHistoryComponent } from './medical-history.component';
import { OdontogramPrintComponent } from './odontogram-print.component';

@Component({
  selector: 'app-patient-medical-history-print',
  standalone: true,
  imports: [CommonModule, PrintClinicHeaderComponent, MedicalHistoryComponent, OdontogramPrintComponent],
  templateUrl: './patient-medical-history-print.component.html',
  styleUrls: ['./patient-medical-history-print.component.css', '../../shared/styles/print-document.css'],
})
export class PatientMedicalHistoryPrintComponent implements OnInit {
  loading = signal(true);
  error = signal('');
  patient = signal<Patient | null>(null);
  odontogram = signal<Record<string, ToothData>>({});
  treatments = signal<Treatment[]>([]);
  clinic = signal<ClinicInfo | null>(null);
  doctorName = signal('');

  readonly issuedDate = formatDateLong(new Date().toISOString());

  constructor(
    private route: ActivatedRoute,
    private patientService: PatientService,
    private treatmentService: TreatmentService,
    private clinicService: ClinicService,
    private auth: AuthService,
  ) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.doctorName.set(this.auth.currentUser()?.full_name ?? '');

    forkJoin({
      patient: this.patientService.getById(id),
      odontogram: this.patientService.getOdontogram(id),
      treatments: this.treatmentService.getAll({ patient_id: id, per_page: 200 }),
      clinic: this.clinicService.getInfo(),
    }).subscribe({
      next: ({ patient, odontogram, treatments, clinic }) => {
        this.patient.set(patient.patient);
        this.odontogram.set((odontogram as Record<string, ToothData>) || {});
        this.treatments.set(
          [...(treatments.treatments as Treatment[])].sort(
            (a, b) => new Date(b.performed_at).getTime() - new Date(a.performed_at).getTime()
          )
        );
        this.clinic.set(clinic);
        this.loading.set(false);
      },
      error: () => { this.error.set('No se pudo cargar la historia médica'); this.loading.set(false); },
    });
  }

  formatDate(iso: string): string {
    return formatDateLong(iso);
  }

  print(): void {
    window.print();
  }
}
