export interface ToothData {
  status: string;
  notes: string;
}

export interface StatusOption {
  key: string;
  label: string;
  fill: string;
  stroke: string;
}

export const STATUS_CONFIG: Record<string, { label: string; fill: string; stroke: string }> = {
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

// FDI quadrant arrays (display order: patient's right on the left)
export const Q1 = [18, 17, 16, 15, 14, 13, 12, 11]; // upper right
export const Q2 = [21, 22, 23, 24, 25, 26, 27, 28]; // upper left
export const Q4 = [48, 47, 46, 45, 44, 43, 42, 41]; // lower right
export const Q3 = [31, 32, 33, 34, 35, 36, 37, 38]; // lower left

export const TOOTH_NAMES: Record<number, string> = {
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
