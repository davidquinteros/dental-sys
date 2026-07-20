import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';
import { PlatformService } from '../../core/services/platform.service';
import { Clinic, ClinicDetail, PlatformUser, SubscriptionTier } from '../../core/models';
import { formatDate as fmtDate, formatDateOnly as fmtDateOnly } from '../../core/util/date.util';
import { compressImage } from '../../shared/utils/image-compression';

type LogoKind = 'main' | 'print';

@Component({
  selector: 'app-clinic-detail',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './clinic-detail.component.html',
  styleUrl: './clinic-detail.component.css',
})
export class ClinicDetailComponent implements OnInit, OnDestroy {
  clinicId!: number;
  detail = signal<ClinicDetail | null>(null);
  tiers = signal<SubscriptionTier[]>([]);
  loading = signal(true);

  editMode = signal(false);
  editForm = {
    name: '', is_active: true, subscription_tier_id: null as number | null, subscription_status: '',
    plan_started_at: '', plan_expires_at: '', notes: '',
    address: '', phone: '', email: '',
  };
  savingEdit = signal(false);
  editMessage = signal('');

  logoPreviewUrl: Record<LogoKind, ReturnType<typeof signal<SafeUrl | null>>> = {
    main: signal<SafeUrl | null>(null),
    print: signal<SafeUrl | null>(null),
  };
  uploadingLogo: Record<LogoKind, ReturnType<typeof signal<boolean>>> = {
    main: signal(false),
    print: signal(false),
  };
  logoError: Record<LogoKind, ReturnType<typeof signal<string>>> = {
    main: signal(''),
    print: signal(''),
  };
  private logoObjectUrls: Record<LogoKind, string | null> = { main: null, print: null };

  readonly logoKinds: { kind: LogoKind; label: string }[] = [
    { kind: 'main', label: 'Logo principal' },
    { kind: 'print', label: 'Logo para impresiones' },
  ];

  paymentForm = { amount: null as number | null, payment_date: '', period_start: '', period_end: '', notes: '' };
  savingPayment = signal(false);
  paymentError = signal('');

  resetUserId: number | null = null;
  resettingPassword = signal(false);
  resetResult = signal<{ user: PlatformUser; temporary_password: string } | null>(null);
  resetError = signal('');

  constructor(private route: ActivatedRoute, private platform: PlatformService, private sanitizer: DomSanitizer) {}

  ngOnInit(): void {
    this.clinicId = Number(this.route.snapshot.paramMap.get('id'));
    this.platform.getTiers().subscribe({ next: (r) => this.tiers.set(r.tiers) });
    this.load();
  }

  ngOnDestroy(): void {
    this.revokeLogoUrl('main');
    this.revokeLogoUrl('print');
  }

  load(): void {
    this.loading.set(true);
    this.platform.getClinic(this.clinicId).subscribe({
      next: (d) => {
        this.detail.set(d);
        this.editForm = {
          name: d.clinic.name,
          is_active: d.clinic.is_active,
          subscription_tier_id: d.clinic.subscription_tier_id,
          subscription_status: d.clinic.subscription_status,
          plan_started_at: this.toDateInput(d.clinic.plan_started_at),
          plan_expires_at: this.toDateInput(d.clinic.plan_expires_at),
          notes: d.clinic.notes || '',
          address: d.clinic.address || '',
          phone: d.clinic.phone || '',
          email: d.clinic.email || '',
        };
        this.loading.set(false);
        this.loadLogoPreview('main', !!d.clinic.logo_main_url);
        this.loadLogoPreview('print', !!d.clinic.logo_print_url);
      },
      error: () => this.loading.set(false),
    });
  }

  private loadLogoPreview(kind: LogoKind, exists: boolean): void {
    this.revokeLogoUrl(kind);
    this.logoPreviewUrl[kind].set(null);
    if (!exists) return;
    this.platform.getClinicLogoBlob(this.clinicId, kind).subscribe({
      next: blob => {
        this.logoObjectUrls[kind] = URL.createObjectURL(blob);
        this.logoPreviewUrl[kind].set(this.sanitizer.bypassSecurityTrustUrl(this.logoObjectUrls[kind]!));
      },
      error: () => {},
    });
  }

  private revokeLogoUrl(kind: LogoKind): void {
    if (this.logoObjectUrls[kind]) {
      URL.revokeObjectURL(this.logoObjectUrls[kind]!);
      this.logoObjectUrls[kind] = null;
    }
  }

  async onLogoSelected(kind: LogoKind, event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    input.value = '';

    this.uploadingLogo[kind].set(true);
    this.logoError[kind].set('');
    try {
      const { blob, filename } = await compressImage(file, 400, 0.85);
      await firstValueFrom(this.platform.uploadClinicLogo(this.clinicId, kind, blob, filename));
      this.uploadingLogo[kind].set(false);
      this.load();
    } catch {
      this.uploadingLogo[kind].set(false);
      this.logoError[kind].set('No se pudo subir el logo');
    }
  }

  startEdit(): void {
    this.editMessage.set('');
    this.editMode.set(true);
  }

  cancelEdit(): void {
    this.editMode.set(false);
    this.load();
  }

  saveEdit(): void {
    this.savingEdit.set(true);
    this.editMessage.set('');
    this.platform.updateClinic(this.clinicId, {
      ...this.editForm,
      plan_started_at: this.editForm.plan_started_at || null,
      plan_expires_at: this.editForm.plan_expires_at || null,
    }).subscribe({
      next: () => {
        this.savingEdit.set(false);
        this.editMessage.set('Cambios guardados');
        this.editMode.set(false);
        this.load();
      },
      error: () => this.savingEdit.set(false),
    });
  }

  /** ISO datetime (or null) -> yyyy-MM-dd for an <input type="date">. */
  private toDateInput(iso: string | null): string {
    return iso ? iso.substring(0, 10) : '';
  }

  recordPayment(): void {
    if (!this.paymentForm.amount) return;
    this.savingPayment.set(true);
    this.paymentError.set('');
    const payload: any = { amount: this.paymentForm.amount };
    if (this.paymentForm.payment_date) payload.payment_date = this.paymentForm.payment_date;
    if (this.paymentForm.period_start) payload.period_start = this.paymentForm.period_start;
    if (this.paymentForm.period_end) payload.period_end = this.paymentForm.period_end;
    if (this.paymentForm.notes) payload.notes = this.paymentForm.notes;

    this.platform.recordPayment(this.clinicId, payload).subscribe({
      next: () => {
        this.savingPayment.set(false);
        this.paymentForm = { amount: null, payment_date: '', period_start: '', period_end: '', notes: '' };
        this.load();
      },
      error: (err) => {
        this.paymentError.set(err.error?.error || 'Error al registrar el pago');
        this.savingPayment.set(false);
      },
    });
  }

  resetPassword(): void {
    this.resettingPassword.set(true);
    this.resetError.set('');
    this.resetResult.set(null);
    this.platform.resetAdminPassword(this.clinicId, this.resetUserId ?? undefined).subscribe({
      next: (r) => {
        this.resetResult.set(r);
        this.resettingPassword.set(false);
      },
      error: (err) => {
        this.resetError.set(err.error?.error || 'Error al restaurar la contraseña');
        this.resettingPassword.set(false);
      },
    });
  }

  formatDate(iso: string | null): string { return iso ? fmtDate(iso) : '—'; }
  formatDateOnly(iso: string | null): string { return iso ? fmtDateOnly(iso) : '—'; }

  daysRemaining(iso: string | null): { label: string; cssClass: string } {
    if (!iso) return { label: '—', cssClass: 'text-muted' };
    const days = Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
    if (days < 0) return { label: `Vencido hace ${-days} día${-days === 1 ? '' : 's'}`, cssClass: 'text-danger' };
    if (days === 0) return { label: 'Vence hoy', cssClass: 'text-danger' };
    if (days <= 7) return { label: `${days} día${days === 1 ? '' : 's'}`, cssClass: 'text-warning' };
    return { label: `${days} días`, cssClass: '' };
  }
}
