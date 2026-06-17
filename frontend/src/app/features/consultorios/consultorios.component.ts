import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ConsultorioService } from '../../core/services/api.service';
import { Consultorio } from '../../core/models';

const PRESET_COLORS = [
  '#4299e1', '#319795', '#805ad5', '#dd6b20',
  '#38a169', '#d53f8c', '#e53e3e', '#b7791f',
];

@Component({
  selector: 'app-consultorios',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './consultorios.component.html',
  styleUrl: './consultorios.component.css',
})
export class ConsultoriosComponent implements OnInit {
  loading    = signal(true);
  saving     = signal(false);
  successMsg = signal('');
  errorMsg   = signal('');

  consultorios = signal<Consultorio[]>([]);
  showForm     = signal(false);
  editId       = signal<number | null>(null);

  newItem = { name: '', description: '', color: '#4299e1' };
  editItem = { name: '', description: '', color: '#4299e1' };

  readonly presetColors = PRESET_COLORS;

  constructor(private service: ConsultorioService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.service.getAll().subscribe({
      next: res => { this.consultorios.set(res.consultorios); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  // ── Create ─────────────────────────────────────────────────────────────────

  openForm(): void {
    this.newItem = { name: '', description: '', color: '#4299e1' };
    this.showForm.set(true);
    this.errorMsg.set('');
  }

  submitNew(): void {
    if (!this.newItem.name.trim()) { this.errorMsg.set('El nombre es requerido'); return; }
    this.saving.set(true);
    this.service.create(this.newItem).subscribe({
      next: () => {
        this.showForm.set(false);
        this.saving.set(false);
        this.flash('Consultorio creado correctamente');
        this.load();
      },
      error: err => { this.errorMsg.set(err.error?.error || 'Error al crear'); this.saving.set(false); },
    });
  }

  // ── Edit ───────────────────────────────────────────────────────────────────

  startEdit(c: Consultorio): void {
    this.editId.set(c.id);
    this.editItem = { name: c.name, description: c.description ?? '', color: c.color };
  }

  cancelEdit(): void { this.editId.set(null); }

  saveEdit(c: Consultorio): void {
    if (!this.editItem.name.trim()) return;
    this.service.update(c.id, this.editItem).subscribe({
      next: () => { this.editId.set(null); this.flash('Actualizado'); this.load(); },
      error: err => this.errorMsg.set(err.error?.error || 'Error al actualizar'),
    });
  }

  // ── Delete ─────────────────────────────────────────────────────────────────

  remove(c: Consultorio): void {
    if (!confirm(`¿Desactivar el "${c.name}"? Las citas existentes no se verán afectadas.`)) return;
    this.service.delete(c.id).subscribe({
      next: () => { this.flash('Consultorio desactivado'); this.load(); },
      error: err => this.errorMsg.set(err.error?.error || 'Error al eliminar'),
    });
  }

  private flash(msg: string): void {
    this.successMsg.set(msg);
    setTimeout(() => this.successMsg.set(''), 3000);
  }
}
