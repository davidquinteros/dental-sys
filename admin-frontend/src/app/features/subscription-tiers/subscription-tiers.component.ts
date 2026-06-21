import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PlatformService } from '../../core/services/platform.service';
import { SubscriptionTier } from '../../core/models';

@Component({
  selector: 'app-subscription-tiers',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './subscription-tiers.component.html',
  styleUrl: './subscription-tiers.component.css',
})
export class SubscriptionTiersComponent implements OnInit {
  tiers = signal<SubscriptionTier[]>([]);
  loading = signal(true);
  showForm = signal(false);
  saving = signal(false);
  error = signal('');

  form = { name: '', code: '', monthly_price: null as number | null, max_users: null as number | null, description: '' };

  constructor(private platform: PlatformService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.platform.getTiers().subscribe({
      next: (r) => { this.tiers.set(r.tiers); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  toggleForm(): void {
    this.showForm.set(!this.showForm());
    this.error.set('');
  }

  onSubmit(): void {
    if (!this.form.name || !this.form.code || this.form.monthly_price === null) return;
    this.saving.set(true);
    this.error.set('');
    this.platform.createTier({
      name: this.form.name,
      code: this.form.code,
      monthly_price: this.form.monthly_price,
      max_users: this.form.max_users,
      description: this.form.description || undefined,
    }).subscribe({
      next: () => {
        this.saving.set(false);
        this.showForm.set(false);
        this.form = { name: '', code: '', monthly_price: null, max_users: null, description: '' };
        this.load();
      },
      error: (err) => {
        this.error.set(err.error?.error || 'Error al crear el plan');
        this.saving.set(false);
      },
    });
  }

  toggleActive(tier: SubscriptionTier): void {
    this.platform.updateTier(tier.id, { is_active: !tier.is_active }).subscribe({ next: () => this.load() });
  }
}
