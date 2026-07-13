import { Component, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ConfirmService } from '../../../core/services/confirm.service';

/**
 * Renders the app-wide confirmation dialog driven by ConfirmService. Mounted once
 * at the app root (app.component.html) so any component can trigger it via the
 * service without wiring up its own modal. See ConfirmService for usage.
 */
@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './confirm-dialog.component.html',
  styleUrl: './confirm-dialog.component.css',
})
export class ConfirmDialogComponent {
  constructor(public confirmService: ConfirmService) {}

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.confirmService.state()) this.confirmService.respond(false);
  }
}
