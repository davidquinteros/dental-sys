import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { PlatformService } from '../../core/services/platform.service';
import { Clinic, SubscriptionTier } from '../../core/models';

@Component({
  selector: 'app-clinics-list',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './clinics-list.component.html',
  styleUrl: './clinics-list.component.css',
})
export class ClinicsListComponent implements OnInit {
  clinics = signal<Clinic[]>([]);
  tiers = signal<SubscriptionTier[]>([]);
  loading = signal(true);
  showForm = signal(false);
  saving = signal(false);
  error = signal('');

  form = {
    name: '', admin_email: '', admin_password: '',
    admin_first_name: 'Admin', admin_last_name: '', subscription_tier_id: null as number | null,
  };

  constructor(private platform: PlatformService) {}

  ngOnInit(): void {
    this.loadClinics();
    this.platform.getTiers().subscribe({ next: (r) => this.tiers.set(r.tiers) });
  }

  loadClinics(): void {
    this.loading.set(true);
    this.platform.getClinics().subscribe({
      next: (r) => { this.clinics.set(r.clinics); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  toggleForm(): void {
    this.showForm.set(!this.showForm());
    this.error.set('');
  }

  onSubmit(): void {
    if (!this.form.name || !this.form.admin_email || !this.form.admin_password) return;
    this.saving.set(true);
    this.error.set('');
    this.platform.createClinic(this.form).subscribe({
      next: () => {
        this.saving.set(false);
        this.showForm.set(false);
        this.form = { name: '', admin_email: '', admin_password: '', admin_first_name: 'Admin', admin_last_name: '', subscription_tier_id: null };
        this.loadClinics();
      },
      error: (err) => {
        this.error.set(err.error?.error || 'Error al crear la clínica');
        this.saving.set(false);
      },
    });
  }

  formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'short', year: 'numeric' });
  }
}
