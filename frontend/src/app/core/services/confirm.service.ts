import { Injectable, signal } from '@angular/core';

export interface ConfirmOptions {
  /** Main body text (required). */
  message: string;
  /** Heading above the message. Defaults to "Confirmar". */
  title?: string;
  /** Label of the accept button. Defaults to "Aceptar". */
  confirmText?: string;
  /** Label of the cancel button. Defaults to "Cancelar". */
  cancelText?: string;
  /** When true the accept button is styled as a destructive/red action. */
  danger?: boolean;
}

interface ConfirmState extends Required<Omit<ConfirmOptions, 'danger'>> {
  danger: boolean;
}

/**
 * App-wide confirmation dialog, a professional replacement for the native
 * `window.confirm()`. Call `confirm(...)` and await the returned promise:
 *
 *   if (!(await this.confirmService.confirm('¿Eliminar?'))) return;
 *
 * A single <app-confirm-dialog/> mounted at the app root (app.component.html)
 * renders whatever this service holds; only one dialog can be open at a time.
 */
@Injectable({ providedIn: 'root' })
export class ConfirmService {
  private readonly _state = signal<ConfirmState | null>(null);
  /** Current dialog to render, or null when none is open. Read by the dialog component. */
  readonly state = this._state.asReadonly();

  private resolver: ((accepted: boolean) => void) | null = null;

  confirm(opts: string | ConfirmOptions): Promise<boolean> {
    const o: ConfirmOptions = typeof opts === 'string' ? { message: opts } : opts;
    // If a dialog is somehow already open, resolve it as cancelled first.
    this.resolver?.(false);
    this._state.set({
      message: o.message,
      title: o.title ?? 'Confirmar',
      confirmText: o.confirmText ?? 'Aceptar',
      cancelText: o.cancelText ?? 'Cancelar',
      danger: o.danger ?? false,
    });
    return new Promise<boolean>(resolve => { this.resolver = resolve; });
  }

  /** Called by the dialog component when the user picks an option (or dismisses). */
  respond(accepted: boolean): void {
    if (!this._state()) return;
    this._state.set(null);
    const r = this.resolver;
    this.resolver = null;
    r?.(accepted);
  }
}
