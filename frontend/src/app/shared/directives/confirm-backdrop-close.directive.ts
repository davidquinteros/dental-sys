import { Directive, EventEmitter, HostListener, Input, Output } from '@angular/core';
import { ConfirmService } from '../../core/services/confirm.service';

/**
 * Put on a modal's backdrop element. A click on the backdrop itself (not on the
 * modal content inside it) pops the app's custom confirm dialog (ConfirmService),
 * and only emits `confirmedClose` if the user accepts — so clicking outside a modal
 * no longer closes it by accident. Replaces a plain `(click)="closeModal()"`.
 *
 *   <div class="modal-backdrop" appConfirmBackdropClose (confirmedClose)="showModal.set(false)">
 *     <div class="modal" (click)="$event.stopPropagation()"> ... </div>
 *   </div>
 *
 * The `event.target === event.currentTarget` guard means inner clicks are ignored
 * even if a child forgets to stopPropagation.
 */
@Directive({
  selector: '[appConfirmBackdropClose]',
  standalone: true,
})
export class ConfirmBackdropCloseDirective {
  /** Message shown in the confirm dialog. Override for read-only modals where
   * there is nothing to lose. */
  @Input() confirmMessage = '¿Deseas cerrar esta ventana? Los cambios sin guardar se perderán.';
  /** Emitted only when the user clicks the backdrop AND confirms. */
  @Output() confirmedClose = new EventEmitter<void>();

  constructor(private confirmService: ConfirmService) {}

  @HostListener('click', ['$event'])
  onBackdropClick(event: MouseEvent): void {
    if (event.target !== event.currentTarget) return; // click landed on modal content, ignore
    this.confirmService
      .confirm({ title: 'Cerrar ventana', message: this.confirmMessage })
      .then(ok => { if (ok) this.confirmedClose.emit(); });
  }
}
