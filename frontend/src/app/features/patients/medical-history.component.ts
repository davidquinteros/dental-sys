import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MedicalHistory } from '../../core/models';

const EMPTY: MedicalHistory = { patologicos: {}, extracciones: {}, no_patologicos: {} };

@Component({
  selector: 'app-medical-history',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './medical-history.component.html',
  styleUrl: './medical-history.component.css',
})
export class MedicalHistoryComponent {
  /** When true, renders as a static read-only summary (no toggles/inputs). */
  @Input() readonly = false;
  @Output() valueChange = new EventEmitter<MedicalHistory>();

  private _value: MedicalHistory = { ...EMPTY };
  @Input() set value(v: MedicalHistory | null | undefined) {
    this._value = {
      patologicos: v?.patologicos ?? {},
      extracciones: v?.extracciones ?? {},
      no_patologicos: v?.no_patologicos ?? {},
    };
  }
  get value(): MedicalHistory { return this._value; }

  readonly patologicosItems = [
    { key: 'cardiovasculares', label: 'Cardiovasculares' },
    { key: 'pulmonares', label: 'Pulmonares' },
    { key: 'renales', label: 'Renales' },
    { key: 'gastrointestinales', label: 'Gastrointestinales' },
    { key: 'hematologicas', label: 'Hematológicas' },
    { key: 'endocrinas', label: 'Endocrinas' },
    { key: 'mentales', label: 'Mentales' },
    { key: 'dermatologicas', label: 'Dermatológicas' },
    { key: 'neurologicas', label: 'Neurológicas' },
    { key: 'metabolicas', label: 'Metabólicas' },
    { key: 'marcapasos', label: 'Marcapasos' },
    { key: 'cardiopatias', label: 'Cardiopatías' },
    { key: 'neuropatias', label: 'Neuropatías' },
    { key: 'implante_dental', label: 'Implante dental' },
    { key: 'cancer', label: 'Cáncer' },
    { key: 'convulsiones', label: 'Convulsiones' },
  ];

  readonly extraccionesItems = [
    { key: 'se_ha_realizado', label: '¿Se ha realizado extracciones antes?' },
    { key: 'problemas_despues', label: '¿Hubo problemas después de las extracciones?' },
    { key: 'hemorragia_excesiva', label: '¿Ha padecido de hemorragia excesiva después de una extracción o traumatismo?' },
  ];

  readonly noPatologicosItems = [
    { key: 'tabaquismo', label: 'Tabaquismo' },
    { key: 'alcoholismo', label: 'Alcoholismo' },
    { key: 'toxicomanias', label: 'Toxicomanías' },
    { key: 'sedentarismo', label: 'Sedentarismo' },
    { key: 'traumatismo', label: 'Traumatismo' },
    { key: 'cirugias', label: 'Cirugías' },
  ];

  hasAnyAnswer(): boolean {
    const groups = [this.value.patologicos, this.value.extracciones, this.value.no_patologicos];
    return groups.some(g => Object.values(g).some(v => v !== null && v !== undefined && v !== ''));
  }

  setBool(group: 'patologicos' | 'extracciones' | 'no_patologicos', key: string, val: boolean): void {
    if (this.readonly) return;
    const current = this.value[group][key];
    this.value[group][key] = current === val ? null : val;
    this.valueChange.emit(this.value);
  }

  onTextChange(): void {
    this.valueChange.emit(this.value);
  }

  answerLabel(v: boolean | string | null | undefined): string {
    if (v === true) return 'Sí';
    if (v === false) return 'No';
    return '—';
  }

  answerClass(v: boolean | string | null | undefined): string {
    if (v === true) return 'ans-yes';
    if (v === false) return 'ans-no';
    return 'ans-none';
  }
}
