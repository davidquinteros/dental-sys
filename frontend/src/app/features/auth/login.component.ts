import { Component, OnInit, signal } from '@angular/core';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent implements OnInit {
  loginForm: FormGroup;
  isLoading = signal(false);
  showPassword = signal(false);
  errorMessage = signal('');

  demoCredentials = [
    { role: 'Admin', email: 'admin@clinica.com', password: 'Admin2025!' },
    { role: 'Doctor', email: 'dr.garcia@clinica.com', password: 'Doctor2025!' },
    { role: 'Recepción', email: 'recepcion@clinica.com', password: 'Recep2025!' },
    { role: 'Asistente', email: 'asistente@clinica.com', password: 'Asist2025!' },
  ];

  // Clínica Demo B (sembrada por `flask seed`) — para mostrar el aislamiento
  // multi-tenant: estos datos nunca se mezclan con los de la clínica de arriba.
  demoCredentialsClinicB = [
    { role: 'Admin', email: 'admin@clinicab.com', password: 'AdminB2025!' },
  ];

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute,
  ) {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required],
    });
  }

  ngOnInit(): void {
    const blocked = this.route.snapshot.queryParamMap.get('blocked');
    if (blocked) this.errorMessage.set(blocked);
  }

  toggleShowPassword(): void {
    this.showPassword.update(v => !v);
  }

  fillCredentials(email: string, password: string): void {
    this.loginForm.patchValue({ email, password });
    this.errorMessage.set('');
  }

  onSubmit(): void {
    if (this.loginForm.invalid) { this.loginForm.markAllAsTouched(); return; }
    this.isLoading.set(true);
    this.errorMessage.set('');
    this.auth.login(this.loginForm.value).subscribe({
      next: () => this.router.navigate(['/dashboard']),
      error: (err) => {
        this.errorMessage.set(err.message || 'Error al iniciar sesión');
        this.isLoading.set(false);
      },
    });
  }
}
