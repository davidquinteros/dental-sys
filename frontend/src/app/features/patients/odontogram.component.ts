import { Component, Input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PatientService } from '../../core/services/api.service';

interface ToothData {
  status: string;
  notes: string;
}

interface StatusOption {
  key: string;
  label: string;
  fill: string;
  stroke: string;
}

const STATUS_CONFIG: Record<string, { label: string; fill: string; stroke: string }> = {
  healthy:            { label: 'Sano',           fill: '#f8fafc', stroke: '#a0aec0' },
  caries:             { label: 'Caries',          fill: '#fed7d7', stroke: '#fc8181' },
  restoration:        { label: 'Restauración',    fill: '#bee3f8', stroke: '#4299e1' },
  crown:              { label: 'Corona',           fill: '#fef3c7', stroke: '#d69e2e' },
  extracted:          { label: 'Extraído',         fill: '#edf2f7', stroke: '#718096' },
  endodontics:        { label: 'Endodoncia',       fill: '#e9d8fd', stroke: '#9f7aea' },
  implant:            { label: 'Implante',         fill: '#c6f6d5', stroke: '#38a169' },
  fracture:           { label: 'Fractura',         fill: '#fde8d0', stroke: '#dd6b20' },
  missing_congenital: { label: 'Ausente',          fill: '#f7fafc', stroke: '#e2e8f0' },
};

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

  // FDI quadrant arrays (display order: patient's right on the left)
  readonly Q1 = [18, 17, 16, 15, 14, 13, 12, 11]; // upper right
  readonly Q2 = [21, 22, 23, 24, 25, 26, 27, 28]; // upper left
  readonly Q4 = [48, 47, 46, 45, 44, 43, 42, 41]; // lower right
  readonly Q3 = [31, 32, 33, 34, 35, 36, 37, 38]; // lower left

  readonly statuses: StatusOption[] = Object.entries(STATUS_CONFIG).map(([key, v]) => ({ key, ...v }));

  private readonly toothNames: Record<number, string> = {
    11: 'Incisivo Central',  12: 'Incisivo Lateral', 13: 'Canino',
    14: 'Premolar 1',        15: 'Premolar 2',
    16: 'Molar 1',           17: 'Molar 2',          18: 'Cordal',
    21: 'Incisivo Central',  22: 'Incisivo Lateral', 23: 'Canino',
    24: 'Premolar 1',        25: 'Premolar 2',
    26: 'Molar 1',           27: 'Molar 2',          28: 'Cordal',
    31: 'Incisivo Central',  32: 'Incisivo Lateral', 33: 'Canino',
    34: 'Premolar 1',        35: 'Premolar 2',
    36: 'Molar 1',           37: 'Molar 2',          38: 'Cordal',
    41: 'Incisivo Central',  42: 'Incisivo Lateral', 43: 'Canino',
    44: 'Premolar 1',        45: 'Premolar 2',
    46: 'Molar 1',           47: 'Molar 2',          48: 'Cordal',
  };

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
