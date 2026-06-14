import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { UserService } from '../../core/services/api.service';
import { User } from '../../core/models';

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
  roleFilter = signal('');
  userForm: FormGroup;

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
      password: ['', [Validators.minLength(8)]],
      role: ['', Validators.required],
      phone: [''],
      specialty: [''],
      license_number: [''],
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
    this.userForm.get('password')?.setValidators([Validators.required, Validators.minLength(8)]);
    this.userForm.get('password')?.updateValueAndValidity();
    this.modalError.set('');
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
  initials(u: User): string { return `${u.first_name[0]}${u.last_name[0]}`.toUpperCase(); }
  roleLabel(r: string): string {
    const m: Record<string, string> = { admin: 'Administrador', doctor: 'Médico', receptionist: 'Recepcionista', assistant: 'Asistente' };
    return m[r] ?? r;
  }
}
