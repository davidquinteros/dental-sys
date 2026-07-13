import { Component, DestroyRef, Input, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormGroup } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

/**
 * Reusable "condiciones" fields for a fixed cost-per-cita billing document —
 * used today by the payment plan form (FCLI-13) and meant to be reused as-is
 * by the presupuesto form (FCLI-14). The parent must build a FormGroup with
 * EXACTLY these controls and pass it in as `form` (same instance, no
 * ControlValueAccessor involved):
 *   calc_mode:     'per_cita' | 'total'
 *   num_citas:     number
 *   cost_per_cita: number
 *   total_amount:  number
 *   down_payment:  number
 *   start_date:    string (yyyy-mm-dd)
 *   end_date:      string (yyyy-mm-dd)
 * In 'per_cita' mode the user enters cost_per_cita and total_amount is
 * derived; in 'total' mode the user enters total_amount and cost_per_cita is
 * derived. The parent reads `form.value` as usual — no controls are ever
 * disabled, only shown read-only, so nothing is excluded from `.value`.
 */
@Component({
  selector: 'app-billing-conditions-fields',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './billing-conditions-fields.component.html',
  styleUrl: './billing-conditions-fields.component.css',
})
export class BillingConditionsFieldsComponent implements OnInit {
  @Input() form!: FormGroup;
  /** When true, cost-related fields (calc_mode/cost_per_cita/total_amount/down_payment)
   * are shown read-only — used once a plan/presupuesto already has payments registered
   * and the backend rejects changes to the fixed cost. `num_citas` and the date range
   * stay editable. */
  @Input() costLocked = false;
  /** When true, the calc-mode toggle is locked to 'total' (the "Por costo de cita" option
   * is disabled) — only the "Por monto total" flow is offered for now. Parents must also
   * set the form's calc_mode to 'total'; this just enforces it in the UI/display. */
  @Input() lockToTotal = false;
  /** When true, the "Monto Total" input is shown read-only — used when the total is
   * driven externally (e.g. the presupuesto's items subtotal) rather than typed. */
  @Input() totalReadonly = false;
  private destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    if (this.lockToTotal && this.form.get('calc_mode')?.value !== 'total') {
      this.form.get('calc_mode')?.setValue('total', { emitEvent: false });
    }
    this.form.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.recalculate());
    this.recalculate();
  }

  isPerCita(): boolean {
    // lockToTotal wins over the stored value so the display can never get stuck showing
    // per-cita mode with a disabled toggle.
    return !this.lockToTotal && this.form.get('calc_mode')?.value === 'per_cita';
  }

  setCalcMode(mode: 'per_cita' | 'total'): void {
    if (this.costLocked || this.lockToTotal || this.form.get('calc_mode')?.value === mode) return;
    this.form.get('calc_mode')?.setValue(mode);
  }

  formatMoney(val: number): string {
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val || 0);
  }

  private recalculate(): void {
    const numCitas = parseInt(this.form.get('num_citas')?.value, 10) || 0;
    const down = parseFloat(this.form.get('down_payment')?.value) || 0;
    if (numCitas <= 0) return;

    if (this.isPerCita()) {
      const costPerCita = parseFloat(this.form.get('cost_per_cita')?.value) || 0;
      const total = Math.round((down + numCitas * costPerCita) * 100) / 100;
      if (this.form.get('total_amount')?.value !== total) {
        this.form.get('total_amount')?.setValue(total, { emitEvent: false });
      }
    } else {
      const total = parseFloat(this.form.get('total_amount')?.value) || 0;
      const costPerCita = Math.round(((total - down) / numCitas) * 100) / 100;
      if (this.form.get('cost_per_cita')?.value !== costPerCita) {
        this.form.get('cost_per_cita')?.setValue(costPerCita, { emitEvent: false });
      }
    }
  }
}
