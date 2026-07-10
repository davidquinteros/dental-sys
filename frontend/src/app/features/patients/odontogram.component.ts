import { Component, Input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PatientService } from '../../core/services/api.service';
import {
  ToothData, StatusOption, STATUS_CONFIG,
  Q1 as ODONTO_Q1, Q2 as ODONTO_Q2, Q3 as ODONTO_Q3, Q4 as ODONTO_Q4,
  TOOTH_NAMES,
} from './odontogram-data';

@Component({
  selector: 'app-odontogram',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './odontogram.component.html',
  styleUrl: './odontogram.component.css',
})
export class OdontogramComponent implements OnInit {
  @Input() patientId!: number;

  loading   = signal(true);
  saving    = signal(false);
  successMsg = signal('');
  errorMsg   = signal('');

  odontogram    = signal<Record<string, ToothData>>({});
  selectedTooth = signal<string | null>(null);
  editStatus    = signal('healthy');
  editNotes     = signal('');

  // FDI quadrant arrays (display order: patient's right on the left) — from odontogram-data.ts
  readonly Q1 = ODONTO_Q1;
  readonly Q2 = ODONTO_Q2;
  readonly Q4 = ODONTO_Q4;
  readonly Q3 = ODONTO_Q3;

  readonly statuses: StatusOption[] = Object.entries(STATUS_CONFIG).map(([key, v]) => ({ key, ...v }));

  private readonly toothNames: Record<number, string> = TOOTH_NAMES;

  constructor(private patientService: PatientService) {}

  ngOnInit(): void {
    this.patientService.getOdontogram(this.patientId).subscribe({
      next: (data) => { this.odontogram.set((data as Record<string, ToothData>) || {}); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  // ── Tooth data accessors ───────────────────────────────────────────────────

  getToothData(tooth: number): ToothData {
    return this.odontogram()[String(tooth)] ?? { status: 'healthy', notes: '' };
  }

  getFill(tooth: number): string {
    return STATUS_CONFIG[this.getToothData(tooth).status]?.fill ?? STATUS_CONFIG['healthy'].fill;
  }

  getStroke(tooth: number): string {
    return STATUS_CONFIG[this.getToothData(tooth).status]?.stroke ?? STATUS_CONFIG['healthy'].stroke;
  }

  isExtracted(tooth: number): boolean {
    const s = this.getToothData(tooth).status;
    return s === 'extracted' || s === 'missing_congenital';
  }

  hasNotes(tooth: number): boolean {
    return !!this.getToothData(tooth).notes?.trim();
  }

  isSelected(tooth: number): boolean {
    return this.selectedTooth() === String(tooth);
  }

  getToothName(tooth: number): string {
    return this.toothNames[tooth] ?? `Diente ${tooth}`;
  }

  getStatusLabel(status: string): string {
    return STATUS_CONFIG[status]?.label ?? status;
  }

  // ── Edit panel ─────────────────────────────────────────────────────────────

  selectTooth(tooth: number): void {
    const data = this.getToothData(tooth);
    this.selectedTooth.set(String(tooth));
    this.editStatus.set(data.status || 'healthy');
    this.editNotes.set(data.notes || '');
    this.errorMsg.set('');
  }

  cancelEdit(): void {
    this.selectedTooth.set(null);
  }

  saveTooth(): void {
    const key = this.selectedTooth();
    if (!key) return;
    const updated: Record<string, ToothData> = {
      ...this.odontogram(),
      [key]: { status: this.editStatus(), notes: this.editNotes() },
    };
    this.saving.set(true);
    this.patientService.saveOdontogram(this.patientId, updated).subscribe({
      next: (data) => {
        this.odontogram.set(data as Record<string, ToothData>);
        this.saving.set(false);
        this.selectedTooth.set(null);
        this.successMsg.set('Guardado');
        setTimeout(() => this.successMsg.set(''), 2000);
      },
      error: () => {
        this.errorMsg.set('Error al guardar');
        this.saving.set(false);
      },
    });
  }

  // Expose STATUS_CONFIG to template
  readonly statusConfig = STATUS_CONFIG;
}
