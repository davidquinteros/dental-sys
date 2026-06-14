import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { TreatmentService } from '../../core/services/api.service';
import { TreatmentPlan } from '../../core/models';

@Component({
  selector: 'app-treatment-plan-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './treatment-plan-detail.component.html',
  styleUrl: './treatment-plan-detail.component.css',
})
export class TreatmentPlanDetailComponent implements OnInit {
  plan = signal<TreatmentPlan | null>(null);
  loading = signal(true);

  constructor(private route: ActivatedRoute, private treatmentService: TreatmentService) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.treatmentService.getPlan(id, true).subscribe({
      next: res => { this.plan.set(res.treatment_plan); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'short', year: 'numeric' });
  }
  statusLabel(s: string): string {
    const m: Record<string, string> = { active: 'Activo', completed: 'Completado', cancelled: 'Cancelado', on_hold: 'En pausa' };
    return m[s] ?? s;
  }
}
