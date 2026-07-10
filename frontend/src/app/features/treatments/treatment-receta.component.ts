import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { TreatmentService, PatientService, UserService, ClinicService } from '../../core/services/api.service';
import { Treatment, Patient, ClinicInfo } from '../../core/models';

@Component({
  selector: 'app-treatment-receta',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './treatment-receta.component.html',
  styleUrl: './treatment-receta.component.css',
})
export class TreatmentRecetaComponent implements OnInit, OnDestroy {
  loading = signal(true);
  error = signal('');
  treatment = signal<Treatment | null>(null);
  patient = signal<Patient | null>(null);
  clinic = signal<ClinicInfo | null>(null);
  doctorSpecialty = signal('');
  logoUrl = signal<SafeUrl | null>(null);

  private logoObjectUrl: string | null = null;

  constructor(
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    private patientService: PatientService,
    private userService: UserService,
    private clinicService: ClinicService,
    private sanitizer: DomSanitizer,
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
            if (clinic.logo_url) this.loadLogo();
          },
          error: () => { this.error.set('No se pudo cargar la información de la receta'); this.loading.set(false); },
        });
      },
      error: () => { this.error.set('Atención no encontrada'); this.loading.set(false); },
    });
  }

  ngOnDestroy(): void {
    if (this.logoObjectUrl) URL.revokeObjectURL(this.logoObjectUrl);
  }

  private loadLogo(): void {
    this.clinicService.getLogoBlob().subscribe({
      next: blob => {
        this.logoObjectUrl = URL.createObjectURL(blob);
        this.logoUrl.set(this.sanitizer.bypassSecurityTrustUrl(this.logoObjectUrl));
      },
      error: () => {},
    });
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'long', year: 'numeric' });
  }

  print(): void {
    window.print();
  }
}
