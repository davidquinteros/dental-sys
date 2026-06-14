import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { TreatmentService } from '../../core/services/api.service';
import { Treatment } from '../../core/models';

@Component({
  selector: 'app-treatment-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './treatment-detail.component.html',
  styleUrl: './treatment-detail.component.css',
})
export class TreatmentDetailComponent implements OnInit {
  treatment = signal<Treatment | null>(null);
  loading = signal(true);

  constructor(private route: ActivatedRoute, private treatmentService: TreatmentService) {}

  ngOnInit(): void {
    const id = +this.route.snapshot.paramMap.get('id')!;
    this.treatmentService.getAll({ per_page: 1 }); // warm up
    // Use the list endpoint filtered by id for now
    this.treatmentService.getAll({ per_page: 100 }).subscribe({
      next: res => {
        const t = res.treatments.find((t: any) => t.id === id);
        this.treatment.set(t || null);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'long', year: 'numeric' });
  }
  formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString('es-BO', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
}
