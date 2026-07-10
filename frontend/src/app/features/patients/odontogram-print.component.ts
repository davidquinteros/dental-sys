import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ToothData, StatusOption, STATUS_CONFIG,
  Q1 as ODONTO_Q1, Q2 as ODONTO_Q2, Q3 as ODONTO_Q3, Q4 as ODONTO_Q4,
  TOOTH_NAMES,
} from './odontogram-data';

/** Presentational, read-only odontogram for printable documents: no click handlers, no edit panel, no PatientService call — the parent passes already-loaded data. */
@Component({
  selector: 'app-odontogram-print',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './odontogram-print.component.html',
  styleUrl: './odontogram-print.component.css',
})
export class OdontogramPrintComponent {
  @Input() odontogram: Record<string, ToothData> = {};

  readonly Q1 = ODONTO_Q1;
  readonly Q2 = ODONTO_Q2;
  readonly Q4 = ODONTO_Q4;
  readonly Q3 = ODONTO_Q3;
  readonly statuses: StatusOption[] = Object.entries(STATUS_CONFIG).map(([key, v]) => ({ key, ...v }));

  private getToothData(tooth: number): ToothData {
    return this.odontogram[String(tooth)] ?? { status: 'healthy', notes: '' };
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

  getToothName(tooth: number): string {
    return TOOTH_NAMES[tooth] ?? `Diente ${tooth}`;
  }

  getStatusLabel(tooth: number): string {
    return STATUS_CONFIG[this.getToothData(tooth).status]?.label ?? this.getToothData(tooth).status;
  }
}
