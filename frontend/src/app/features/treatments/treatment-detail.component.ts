import { Component, EventEmitter, Input, OnInit, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { TreatmentService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Treatment } from '../../core/models';
import { TreatmentImagesComponent } from './treatment-images.component';

@Component({
  selector: 'app-treatment-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, TreatmentImagesComponent],
  templateUrl: './treatment-detail.component.html',
  styleUrl: './treatment-detail.component.css',
})
export class TreatmentDetailComponent implements OnInit {
  /** When true, renders without page chrome (no breadcrumb/page actions) and emits (closed) instead of navigating. */
  @Input() embedded = false;
  /** Treatment to load in embedded mode (ignored when routed — that mode reads the id from the URL). */
  @Input() treatmentId: number | null = null;
  @Output() closed = new EventEmitter<void>();

  treatment = signal<Treatment | null>(null);
  loading = signal(true);

  constructor(
    private route: ActivatedRoute,
    private treatmentService: TreatmentService,
    public auth: AuthService,
  ) {}

  ngOnInit(): void {
    const id = this.embedded ? this.treatmentId! : +this.route.snapshot.paramMap.get('id')!;
    this.treatmentService.getById(id).subscribe({
      next: res => { this.treatment.set(res.treatment); this.loading.set(false); },
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
