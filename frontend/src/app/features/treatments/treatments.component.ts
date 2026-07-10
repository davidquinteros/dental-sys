import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { TreatmentService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Treatment, TreatmentPlan } from '../../core/models';
import { formatDate as fmtDate, formatDateOnly as fmtDateOnly } from '../../core/util/date.util';

@Component({
  selector: 'app-treatments',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './treatments.component.html',
  styleUrl: './treatments.component.css',
})
export class TreatmentsComponent implements OnInit {
  view = signal<'treatments' | 'plans'>('treatments');
  treatments = signal<Treatment[]>([]);
  plans = signal<TreatmentPlan[]>([]);
  loadingTreatments = signal(true);
  loadingPlans = signal(true);

  constructor(
    private treatmentService: TreatmentService,
    public auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.treatmentService.getAll({ per_page: 50 }).subscribe({
      next: res => { this.treatments.set(res.treatments); this.loadingTreatments.set(false); },
      error: () => this.loadingTreatments.set(false),
    });
    this.treatmentService.getPlans({ per_page: 50 }).subscribe({
      next: res => { this.plans.set(res.treatment_plans); this.loadingPlans.set(false); },
      error: () => this.loadingPlans.set(false),
    });
  }

  formatDate(iso: string): string { return fmtDate(iso); }
  formatDateOnly(iso: string): string { return fmtDateOnly(iso); }

  planStatusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', on_hold: 'En pausa' };
    return m[s] ?? s;
  }
}
