import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { TreatmentService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { TreatmentPlan } from '../../core/models';
import { formatDate as fmtDate, formatDateOnly as fmtDateOnly } from '../../core/util/date.util';
import { TreatmentImagesComponent } from './treatment-images.component';

@Component({
  selector: 'app-treatment-plan-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, TreatmentImagesComponent],
  templateUrl: './treatment-plan-detail.component.html',
  styleUrl: './treatment-plan-detail.component.css',
})
export class TreatmentPlanDetailComponent implements OnInit {
  plan = signal<TreatmentPlan | null>(null);
  loading = signal(true);

  constructor(
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    public auth: AuthService,
  ) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.treatmentService.getPlan(id, true).subscribe({
      next: res => { this.plan.set(res.treatment_plan); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  formatDate(iso: string): string { return fmtDate(iso); }
  formatDateOnly(iso: string): string { return fmtDateOnly(iso); }
  statusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', on_hold: 'En pausa' };
    return m[s] ?? s;
  }
}
