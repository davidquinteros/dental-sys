import { Component, Input, OnChanges, OnDestroy, SimpleChanges, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { ClinicService } from '../../../core/services/api.service';
import { ClinicInfo } from '../../../core/models';

/**
 * Shared header for any printable document (recetario, historia médica, ...):
 * clinic logo/name/address/phone/email, plus an optional document title and
 * issued-date line. `documentTitle`/`issuedDate` are optional and only render
 * when passed, so consumers that never had them (the recetario) look unchanged.
 */
@Component({
  selector: 'app-print-clinic-header',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './print-clinic-header.component.html',
  styleUrl: './print-clinic-header.component.css',
})
export class PrintClinicHeaderComponent implements OnChanges, OnDestroy {
  @Input() clinic!: ClinicInfo;
  @Input() documentTitle?: string;
  @Input() issuedDate?: string;

  logoUrl = signal<SafeUrl | null>(null);
  private logoObjectUrl: string | null = null;

  constructor(private clinicService: ClinicService, private sanitizer: DomSanitizer) {}

  get contactLine(): string {
    const parts = [
      this.clinic?.address,
      this.clinic?.phone ? `Tel: ${this.clinic.phone}` : null,
      this.clinic?.email,
    ].filter(Boolean);
    return parts.join(' · ');
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['clinic'] && this.clinic?.logo_print_url) {
      this.loadLogo();
    }
  }

  ngOnDestroy(): void {
    if (this.logoObjectUrl) URL.revokeObjectURL(this.logoObjectUrl);
  }

  private loadLogo(): void {
    if (this.logoObjectUrl) URL.revokeObjectURL(this.logoObjectUrl);
    this.clinicService.getLogoBlob('print').subscribe({
      next: blob => {
        this.logoObjectUrl = URL.createObjectURL(blob);
        this.logoUrl.set(this.sanitizer.bypassSecurityTrustUrl(this.logoObjectUrl));
      },
      error: () => {},
    });
  }
}
