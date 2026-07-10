import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { TreatmentService, PatientService, UserService, ClinicService } from '../../core/services/api.service';
import { Treatment, Patient, ClinicInfo } from '../../core/models';
import { formatDateLong as fmtDateLong } from '../../core/util/date.util';
import { PrintClinicHeaderComponent } from '../../shared/components/print-clinic-header/print-clinic-header.component';

@Component({
  selector: 'app-treatment-receta',
  standalone: true,
  imports: [CommonModule, PrintClinicHeaderComponent],
  templateUrl: './treatment-receta.component.html',
  styleUrls: ['./treatment-receta.component.css', '../../shared/styles/print-document.css'],
})
export class TreatmentRecetaComponent implements OnInit {
  loading = signal(true);
  error = signal('');
  treatment = signal<Treatment | null>(null);
  patient = signal<Patient | null>(null);
  clinic = signal<ClinicInfo | null>(null);
  doctorSpecialty = signal('');

  constructor(
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    private patientService: PatientService,
    private userService: UserService,
    private clinicService: ClinicService,
  ) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.treatmentService.getById(id).subscribe({
      next: res => {
        const t = res.treatment;
        this.treatment.set(t);
        forkJoin({
          patient: this.patientService.getById(t.patient_id),
          doctors: this.userService.getDoctors(),
          clinic: this.clinicService.getInfo(),
        }).subscribe({
          next: ({ patient, doctors, clinic }) => {
            this.patient.set(patient.patient);
            this.doctorSpecialty.set(doctors.doctors.find(d => d.id === t.doctor_id)?.specialty ?? '');
            this.clinic.set(clinic);
            this.loading.set(false);
          },
          error: () => { this.error.set('No se pudo cargar la información de la receta'); this.loading.set(false); },
        });
      },
      error: () => { this.error.set('Atención no encontrada'); this.loading.set(false); },
    });
  }

  formatDate(iso: string): string { return fmtDateLong(iso); }

  print(): void {
    window.print();
  }
}
