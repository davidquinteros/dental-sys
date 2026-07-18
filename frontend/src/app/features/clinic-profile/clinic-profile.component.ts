import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { ClinicService } from '../../core/services/api.service';
import { ClinicInfo } from '../../core/models';
import { compressImage } from '../../shared/utils/image-compression';

type LogoKind = 'main' | 'print';

/**
 * Clinic self-service profile. All staff can view (name read-only + contact
 * fields + both logos); only the admin sees the "Editar" button and can change
 * contact fields / upload logos. Editing is gated twice — this template's
 * auth.isAdmin() is UX only; the backend's admin_required (FCLI-19) is the real
 * gate. Logo uploads are immediate on file select (no wait for "Guardar").
 */
@Component({
  selector: 'app-clinic-profile',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './clinic-profile.component.html',
  styleUrl: './clinic-profile.component.css',
})
export class ClinicProfileComponent implements OnInit, OnDestroy {
  clinic = signal<ClinicInfo | null>(null);
  loading = signal(true);

  editMode = signal(false);
  editForm = { address: '', phone: '', email: '' };
  saving = signal(false);
  message = signal('');
  error = signal('');

  logoPreview: Record<LogoKind, ReturnType<typeof signal<SafeUrl | null>>> = {
    main: signal<SafeUrl | null>(null),
    print: signal<SafeUrl | null>(null),
  };
  uploading: Record<LogoKind, ReturnType<typeof signal<boolean>>> = {
    main: signal(false),
    print: signal(false),
  };
  logoError: Record<LogoKind, ReturnType<typeof signal<string>>> = {
    main: signal(''),
    print: signal(''),
  };
  private objectUrls: Record<LogoKind, string | null> = { main: null, print: null };

  readonly logoKinds: { kind: LogoKind; label: string; hint: string }[] = [
    { kind: 'main', label: 'Logo principal', hint: 'Se muestra en la aplicación (menú lateral).' },
    { kind: 'print', label: 'Logo para impresiones', hint: 'Se imprime en recetas, presupuestos y comprobantes.' },
  ];

  constructor(
    public auth: AuthService,
    private clinicService: ClinicService,
    private sanitizer: DomSanitizer,
  ) {}

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    this.revoke('main');
    this.revoke('print');
  }

  private load(): void {
    this.loading.set(true);
    this.clinicService.getInfo().subscribe({
      next: info => {
        this.applyInfo(info);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  private applyInfo(info: ClinicInfo): void {
    this.clinic.set(info);
    this.editForm = {
      address: info.address || '',
      phone: info.phone || '',
      email: info.email || '',
    };
    this.loadLogoPreview('main', !!info.logo_main_url);
    this.loadLogoPreview('print', !!info.logo_print_url);
  }

  private loadLogoPreview(kind: LogoKind, exists: boolean): void {
    this.revoke(kind);
    this.logoPreview[kind].set(null);
    if (!exists) return;
    this.clinicService.getLogoBlob(kind).subscribe({
      next: blob => {
        this.objectUrls[kind] = URL.createObjectURL(blob);
        this.logoPreview[kind].set(this.sanitizer.bypassSecurityTrustUrl(this.objectUrls[kind]!));
      },
      error: () => {},
    });
  }

  private revoke(kind: LogoKind): void {
    if (this.objectUrls[kind]) {
      URL.revokeObjectURL(this.objectUrls[kind]!);
      this.objectUrls[kind] = null;
    }
  }

  startEdit(): void {
    this.message.set('');
    this.error.set('');
    this.editMode.set(true);
  }

  cancelEdit(): void {
    this.editMode.set(false);
    const info = this.clinic();
    if (info) {
      this.editForm = { address: info.address || '', phone: info.phone || '', email: info.email || '' };
    }
  }

  save(): void {
    this.saving.set(true);
    this.message.set('');
    this.error.set('');
    this.clinicService.updateProfile({
      address: this.editForm.address.trim(),
      phone: this.editForm.phone.trim(),
      email: this.editForm.email.trim(),
    }).subscribe({
      next: info => {
        this.applyInfo(info);
        this.saving.set(false);
        this.editMode.set(false);
        this.message.set('Cambios guardados');
      },
      error: err => {
        this.saving.set(false);
        this.error.set(err.error?.error || 'No se pudieron guardar los cambios');
      },
    });
  }

  async onLogoSelected(kind: LogoKind, event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    input.value = '';

    this.uploading[kind].set(true);
    this.logoError[kind].set('');
    try {
      const { blob, filename } = await compressImage(file, 400, 0.85);
      const info = await firstValueFrom(this.clinicService.uploadLogo(kind, blob, filename));
      this.applyInfo(info);
      // Keep the sidebar brand in sync when the main logo changes.
      if (kind === 'main') this.clinicService.refreshMainLogo();
      this.uploading[kind].set(false);
    } catch {
      this.uploading[kind].set(false);
      this.logoError[kind].set('No se pudo subir el logo');
    }
  }
}
