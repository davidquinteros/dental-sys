import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { PatientService } from '../../core/services/api.service';

@Component({
  selector: 'app-patient-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './patient-form.component.html',
  styleUrl: './patient-form.component.css',
})
export class PatientFormComponent implements OnInit {
  form: FormGroup;
  isEdit = signal(false);
  loading = signal(false);
  saving = signal(false);
  errorMsg = signal('');
  private patientId?: number;

  constructor(
    private fb: FormBuilder,
    private route: ActivatedRoute,
    private router: Router,
    private patientService: PatientService,
  ) {
    this.form = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      document_type: ['CI'],
      document_number: ['', Validators.required],
      date_of_birth: [''],
      gender: [''],
      phone: [''],
      phone_emergency: [''],
      email: ['', Validators.email],
      address: [''],
      city: [''],
      blood_type: ['unknown'],
      allergies: [''],
      medical_notes: [''],
    });
  }

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id && id !== 'new') {
      this.isEdit.set(true);
      this.patientId = +id;
      this.loading.set(true);
      this.patientService.getById(this.patientId).subscribe({
        next: res => {
          const p = res.patient;
          this.form.patchValue({
            ...p,
            date_of_birth: p.date_of_birth ? p.date_of_birth.substring(0, 10) : '',
          });
          this.loading.set(false);
        },
        error: () => { this.loading.set(false); this.router.navigate(['/patients']); },
      });
    }
  }

  hasError(field: string): boolean {
    const c = this.form.get(field);
    return !!(c?.invalid && c?.touched);
  }

  onSubmit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    this.errorMsg.set('');
    const data = this.form.value;
    const req = this.isEdit()
      ? this.patientService.update(this.patientId!, data)
      : this.patientService.create(data);
    req.subscribe({
      next: res => this.router.navigate(['/patients', res.patient.id]),
      error: err => {
        this.errorMsg.set(err.error?.error || 'Error al guardar');
        this.saving.set(false);
      },
    });
  }
}
