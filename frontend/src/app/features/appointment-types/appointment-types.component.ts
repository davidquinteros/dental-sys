import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AppointmentTypeService } from '../../core/services/api.service';
import { AppointmentTypeItem } from '../../core/models';

const PRESET_COLORS = [
  '#4299e1', '#319795', '#805ad5', '#dd6b20',
  '#38a169', '#d53f8c', '#e53e3e', '#b7791f',
  '#2b6cb0', '#718096', '#d69e2e', '#a0aec0',
];

@Component({
  selector: 'app-appointment-types',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './appointment-types.component.html',
  styleUrl: './appointment-types.component.css',
})
export class AppointmentTypesComponent implements OnInit {
  loading    = signal(true);
  saving     = signal(false);
  successMsg = signal('');
  errorMsg   = signal('');

  types    = signal<AppointmentTypeItem[]>([]);
  showForm = signal(false);
  editId   = signal<number | null>(null);

  newItem  = { label: '', color: '#4299e1' };
  editItem = { label: '', color: '#4299e1' };

  readonly presetColors = PRESET_COLORS;

  constructor(private service: AppointmentTypeService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.service.getAdmin().subscribe({
      next: res => { this.types.set(res.appointment_types); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  openForm(): void {
    this.newItem = { label: '', color: '#4299e1' };
    this.showForm.set(true);
    this.errorMsg.set('');
  }

  submitNew(): void {
    if (!this.newItem.label.trim()) { this.errorMsg.set('El nombre es requerido'); return; }
    this.saving.set(true);
    this.service.create(this.newItem).subscribe({
      next: () => {
        this.showForm.set(false);
        this.saving.set(false);
        this.flash('Tipo de cita creado');
        this.load();
      },
      error: err => { this.errorMsg.set(err.error?.error || 'Error al crear'); this.saving.set(false); },
    });
  }

  startEdit(t: AppointmentTypeItem): void {
    this.editId.set(t.id);
    this.editItem = { label: t.label, color: t.color };
  }

  cancelEdit(): void { this.editId.set(null); }

  saveEdit(t: AppointmentTypeItem): void {
    if (!this.editItem.label.trim()) return;
    this.service.update(t.id, this.editItem).subscribe({
      next: () => { this.editId.set(null); this.flash('Actualizado'); this.load(); },
      error: err => this.errorMsg.set(err.error?.error || 'Error al actualizar'),
    });
  }

  remove(t: AppointmentTypeItem): void {
    if (!confirm(`¿Desactivar el tipo "${t.label}"? Las citas existentes no se verán afectadas.`)) return;
    this.service.delete(t.id).subscribe({
      next: () => { this.flash('Tipo desactivado'); this.load(); },
      error: err => this.errorMsg.set(err.error?.error || 'Error al desactivar'),
    });
  }

  activate(t: AppointmentTypeItem): void {
    this.service.activate(t.id).subscribe({
      next: () => { this.flash('Tipo reactivado'); this.load(); },
      error: err => this.errorMsg.set(err.error?.error || 'Error al reactivar'),
    });
  }

  private flash(msg: string): void {
    this.successMsg.set(msg);
    setTimeout(() => this.successMsg.set(''), 3000);
  }
}
