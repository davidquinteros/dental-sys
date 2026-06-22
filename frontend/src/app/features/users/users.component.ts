import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { UserService } from '../../core/services/api.service';
import { User } from '../../core/models';

export function passwordStrengthValidator(control: AbstractControl): ValidationErrors | null {
  const value: string = control.value || '';
  if (!value) return null;
  const weak = value.length < 6
    || !/[A-Z]/.test(value)
    || !/[a-z]/.test(value)
    || !/[^A-Za-z0-9]/.test(value);
  return weak ? { weakPassword: true } : null;
}

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './users.component.html',
  styleUrl: './users.component.css',
})
export class UsersComponent implements OnInit {
  users = signal<User[]>([]);
  loading = signal(true);
  showModal = signal(false);
  editingUser = signal<User | null>(null);
  modalSaving = signal(false);
  modalError = signal('');
  showPassword = signal(false);
  roleFilter = signal('');
  userForm: FormGroup;

  resetPasswordUser = signal<User | null>(null);
  resetPasswordForm: FormGroup;
  resetShowPassword = signal(false);
  resetSaving = signal(false);
  resetError = signal('');

  roleTabs = [
    { value: '', label: 'Todos' },
    { value: 'admin', label: 'Administradores' },
    { value: 'doctor', label: 'Médicos' },
    { value: 'receptionist', label: 'Recepcionistas' },
    { value: 'assistant', label: 'Asistentes' },
  ];

  constructor(private fb: FormBuilder, private userService: UserService) {
    this.userForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [passwordStrengthValidator]],
      role: ['', Validators.required],
      phone: [''],
      specialty: [''],
      license_number: [''],
    });

    this.resetPasswordForm = this.fb.group({
      password: ['', [Validators.required, passwordStrengthValidator]],
    });
  }

  ngOnInit(): void { this.loadUsers(); }

  loadUsers(): void {
    this.loading.set(true);
    this.userService.getAll().subscribe({
      next: res => { this.users.set(res.users); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  filteredUsers() {
    const role = this.roleFilter();
    return role ? this.users().filter(u => u.role === role) : this.users();
  }

  filterUsers(): void { /* reactive via filteredUsers() */ }
  countByRole(role: string): number {
    return role ? this.users().filter(u => u.role === role).length : this.users().length;
  }

  openModal(): void {
    this.editingUser.set(null);
    this.userForm.reset({ role: '', phone: '' });
    this.userForm.get('password')?.setValidators([Validators.required, passwordStrengthValidator]);
    this.userForm.get('password')?.updateValueAndValidity();
    this.modalError.set('');
    this.showPassword.set(false);
    this.showModal.set(true);
  }

  editUser(user: User): void {
    this.editingUser.set(user);
    this.userForm.patchValue(user);
    this.userForm.get('password')?.clearValidators();
    this.userForm.get('password')?.updateValueAndValidity();
    this.modalError.set('');
    this.showModal.set(true);
  }

  closeModal(): void { this.showModal.set(false); }

  saveUser(): void {
    if (this.userForm.invalid) { this.userForm.markAllAsTouched(); return; }
    this.modalSaving.set(true);
    this.modalError.set('');
    const val = this.userForm.value;
    const req = this.editingUser()
      ? this.userService.update(this.editingUser()!.id, val)
      : this.userService.create(val);
    req.subscribe({
      next: res => {
        if (this.editingUser()) {
          this.users.update(list => list.map(u => u.id === res.user.id ? res.user : u));
        } else {
          this.users.update(list => [res.user, ...list]);
        }
        this.closeModal();
        this.modalSaving.set(false);
      },
      error: err => {
        this.modalError.set(err.error?.error || 'Error al guardar');
        this.modalSaving.set(false);
      },
    });
  }

  toggleActive(user: User): void {
    this.userService.update(user.id, { is_active: !user.is_active }).subscribe({
      next: res => this.users.update(list => list.map(u => u.id === res.user.id ? res.user : u)),
    });
  }

  hasErr(f: string): boolean { const c = this.userForm.get(f); return !!(c?.invalid && c?.touched); }
  toggleShowPassword(): void { this.showPassword.update(v => !v); }

  openResetPassword(user: User): void {
    this.resetPasswordUser.set(user);
    this.resetPasswordForm.reset();
    this.resetShowPassword.set(false);
    this.resetError.set('');
  }

  closeResetPassword(): void { this.resetPasswordUser.set(null); }
  toggleResetShowPassword(): void { this.resetShowPassword.update(v => !v); }
  hasResetErr(): boolean {
    const c = this.resetPasswordForm.get('password');
    return !!(c?.invalid && c?.touched);
  }

  submitResetPassword(): void {
    if (this.resetPasswordForm.invalid) { this.resetPasswordForm.markAllAsTouched(); return; }
    const user = this.resetPasswordUser();
    if (!user) return;
    this.resetSaving.set(true);
    this.resetError.set('');
    this.userService.resetPassword(user.id, this.resetPasswordForm.value.password).subscribe({
      next: () => {
        this.resetSaving.set(false);
        this.closeResetPassword();
      },
      error: err => {
        this.resetSaving.set(false);
        this.resetError.set(err.error?.error || 'Error al restaurar la contraseña');
      },
    });
  }
  initials(u: User): string { return `${u.first_name?.[0] || ''}${u.last_name?.[0] || ''}`.toUpperCase(); }
  roleLabel(r: string): string {
    const m: Record<string, string> = { admin: 'Administrador', doctor: 'Médico', receptionist: 'Recepcionista', assistant: 'Asistente' };
    return m[r] ?? r;
  }
}
