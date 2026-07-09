import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { PlatformService } from '../../core/services/platform.service';
import { Clinic, ClinicDetail, PlatformUser, SubscriptionTier } from '../../core/models';

@Component({
  selector: 'app-clinic-detail',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './clinic-detail.component.html',
  styleUrl: './clinic-detail.component.css',
})
export class ClinicDetailComponent implements OnInit {
  clinicId!: number;
  detail = signal<ClinicDetail | null>(null);
  tiers = signal<SubscriptionTier[]>([]);
  loading = signal(true);

  editMode = signal(false);
  editForm = {
    name: '', is_active: true, subscription_tier_id: null as number | null, subscription_status: '',
    plan_started_at: '', plan_expires_at: '', notes: '',
    address: '', phone: '', logo_url: '',
  };
  savingEdit = signal(false);
  editMessage = signal('');

  paymentForm = { amount: null as number | null, payment_date: '', period_start: '', period_end: '', notes: '' };
  savingPayment = signal(false);
  paymentError = signal('');

  resetUserId: number | null = null;
  resettingPassword = signal(false);
  resetResult = signal<{ user: PlatformUser; temporary_password: string } | null>(null);
  resetError = signal('');

  constructor(private route: ActivatedRoute, private platform: PlatformService) {}

  ngOnInit(): void {
    this.clinicId = Number(this.route.snapshot.paramMap.get('id'));
    this.platform.getTiers().subscribe({ next: (r) => this.tiers.set(r.tiers) });
    this.load();
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
          logo_url: d.clinic.logo_url || '',
        };
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
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

  formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  daysRemaining(iso: string | null): { label: string; cssClass: string } {
    if (!iso) return { label: '—', cssClass: 'text-muted' };
    const days = Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
    if (days < 0) return { label: `Vencido hace ${-days} día${-days === 1 ? '' : 's'}`, cssClass: 'text-danger' };
    if (days === 0) return { label: 'Vence hoy', cssClass: 'text-danger' };
    if (days <= 7) return { label: `${days} día${days === 1 ? '' : 's'}`, cssClass: 'text-warning' };
    return { label: `${days} días`, cssClass: '' };
  }
}
