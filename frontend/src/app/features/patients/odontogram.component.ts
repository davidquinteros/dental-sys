import { Component, Input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PatientService } from '../../core/services/api.service';
import {
  ToothData, StatusOption, STATUS_CONFIG,
  Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8,
  ALL_TOOTH_NAMES, SupernumerarySlot, SUPERNUMERARY_ADULT, SUPERNUMERARY_LABELS,
} from './odontogram-data';

type ToothId = number | string;

/** Reserved (non-tooth) key inside the odontogram JSON holding per-patient view
 * settings — the show/hide-pediatric flag persists here alongside the teeth. */
const SETTINGS_KEY = '_settings';

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
  savingPrimary = signal(false);
  successMsg = signal('');
  errorMsg   = signal('');

  odontogram    = signal<Record<string, ToothData>>({});
  selectedTooth = signal<string | null>(null);
  editStatus    = signal('healthy');
  editNotes     = signal('');

  /** Whether the primary (child) dentition is shown. Persisted per patient. */
  showPrimary = signal(true);

  // Permanent (always shown) and primary (toggle) quadrants — patient's right on the left.
  readonly Q1 = Q1; readonly Q2 = Q2; readonly Q3 = Q3; readonly Q4 = Q4;
  readonly Q5 = Q5; readonly Q6 = Q6; readonly Q7 = Q7; readonly Q8 = Q8;
  readonly supernumeraries: SupernumerarySlot[] = SUPERNUMERARY_ADULT;

  readonly statuses: StatusOption[] = Object.entries(STATUS_CONFIG).map(([key, v]) => ({ key, ...v }));

  constructor(private patientService: PatientService) {}

  ngOnInit(): void {
    this.patientService.getOdontogram(this.patientId).subscribe({
      next: (data) => {
        const { teeth, showPrimary } = this.split(data as Record<string, any>);
        this.odontogram.set(teeth);
        this.showPrimary.set(showPrimary);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  /** Separate the teeth record from the reserved settings key. */
  private split(data: Record<string, any>): { teeth: Record<string, ToothData>; showPrimary: boolean } {
    const copy = { ...(data || {}) };
    const settings = copy[SETTINGS_KEY];
    delete copy[SETTINGS_KEY];
    return { teeth: copy as Record<string, ToothData>, showPrimary: settings?.showPrimary ?? true };
  }

  /** Merge the teeth record with the current view settings for persistence. */
  private withSettings(teeth: Record<string, ToothData>): Record<string, any> {
    return { ...teeth, [SETTINGS_KEY]: { showPrimary: this.showPrimary() } };
  }

  togglePrimary(value: boolean): void {
    if (this.showPrimary() === value || this.savingPrimary()) return;
    this.showPrimary.set(value);
    this.savingPrimary.set(true);
    this.errorMsg.set('');
    // Persist the setting immediately, per patient.
    this.patientService.saveOdontogram(this.patientId, this.withSettings(this.odontogram())).subscribe({
      next: (data) => {
        this.odontogram.set(this.split(data as Record<string, any>).teeth);
        this.savingPrimary.set(false);
      },
      error: () => {
        this.showPrimary.set(!value); // revert on failure
        this.savingPrimary.set(false);
        this.errorMsg.set('No se pudo guardar la preferencia');
      },
    });
  }

  // ── Tooth data accessors ───────────────────────────────────────────────────

  getToothData(tooth: ToothId): ToothData {
    return this.odontogram()[String(tooth)] ?? { status: 'healthy', notes: '' };
  }

  getFill(tooth: ToothId): string {
    return STATUS_CONFIG[this.getToothData(tooth).status]?.fill ?? STATUS_CONFIG['healthy'].fill;
  }

  getStroke(tooth: ToothId): string {
    return STATUS_CONFIG[this.getToothData(tooth).status]?.stroke ?? STATUS_CONFIG['healthy'].stroke;
  }

  isExtracted(tooth: ToothId): boolean {
    const s = this.getToothData(tooth).status;
    return s === 'extracted' || s === 'missing_congenital';
  }

  hasNotes(tooth: ToothId): boolean {
    return !!this.getToothData(tooth).notes?.trim();
  }

  isSelected(tooth: ToothId): boolean {
    return this.selectedTooth() === String(tooth);
  }

  isSupernumerary(tooth: ToothId): boolean {
    return !!SUPERNUMERARY_LABELS[String(tooth)];
  }

  supLabel(tooth: ToothId): string {
    return SUPERNUMERARY_LABELS[String(tooth)] ?? '';
  }

  getToothName(tooth: ToothId): string {
    const key = String(tooth);
    if (SUPERNUMERARY_LABELS[key]) return `Supernumerario (${SUPERNUMERARY_LABELS[key]})`;
    return ALL_TOOTH_NAMES[+key] ?? `Diente ${key}`;
  }

  getStatusLabel(status: string): string {
    return STATUS_CONFIG[status]?.label ?? status;
  }

  selectedHeading(): string {
    const k = this.selectedTooth();
    if (!k) return '';
    return this.isSupernumerary(k) ? 'Supernumerario' : `Diente ${k}`;
  }

  selectedName(): string {
    const k = this.selectedTooth();
    if (!k) return '';
    return this.isSupernumerary(k) ? this.supLabel(k) : this.getToothName(k);
  }

  // ── Edit panel ─────────────────────────────────────────────────────────────

  selectTooth(tooth: ToothId): void {
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
    const teeth: Record<string, ToothData> = {
      ...this.odontogram(),
      [key]: { status: this.editStatus(), notes: this.editNotes() },
    };
    this.saving.set(true);
    this.patientService.saveOdontogram(this.patientId, this.withSettings(teeth)).subscribe({
      next: (data) => {
        this.odontogram.set(this.split(data as Record<string, any>).teeth);
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
