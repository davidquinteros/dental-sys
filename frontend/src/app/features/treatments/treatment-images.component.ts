import { Component, Input, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';
import { TreatmentService } from '../../core/services/api.service';
import { TreatmentImage } from '../../core/models';
import { compressImage } from '../../shared/utils/image-compression';

/**
 * Reusable clinical-photo gallery. Embed it in a treatment (atención) detail
 * page with [treatmentId], or in a treatment-plan detail page with [planId]
 * (a plan shows every photo of the plan and all its sessions). Handles upload
 * (client-side compressed), thumbnail grid, maximize (lightbox) and delete.
 *
 * Image bytes are fetched through the authenticated API endpoint as Blobs and
 * shown via object URLs — never a public/bucket URL — so confidentiality stays
 * behind the same auth+tenancy layer as the rest of the app.
 */
@Component({
  selector: 'app-treatment-images',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './treatment-images.component.html',
  styleUrl: './treatment-images.component.css',
})
export class TreatmentImagesComponent implements OnInit, OnDestroy {
  @Input() treatmentId: number | null = null;
  @Input() planId: number | null = null;
  /** When false, hides the upload button and delete actions (read-only viewers). */
  @Input() canEdit = true;

  images = signal<TreatmentImage[]>([]);
  thumbUrls = signal<Record<number, SafeUrl>>({});
  loading = signal(true);
  uploading = signal(false);
  error = signal<string | null>(null);
  active = signal<TreatmentImage | null>(null);

  private objectUrls: string[] = [];

  constructor(private svc: TreatmentService, private sanitizer: DomSanitizer) {}

  ngOnInit(): void {
    this.reload();
  }

  ngOnDestroy(): void {
    this.revokeAll();
  }

  private reload(): void {
    const src$ = this.planId != null ? this.svc.listPlanImages(this.planId)
      : this.treatmentId != null ? this.svc.listImages(this.treatmentId)
      : null;
    if (!src$) { this.loading.set(false); return; }

    this.loading.set(true);
    src$.subscribe({
      next: res => {
        this.revokeAll();
        this.thumbUrls.set({});
        this.images.set(res.images);
        this.loading.set(false);
        this.loadThumbs(res.images);
      },
      error: () => {
        this.loading.set(false);
        this.error.set('No se pudieron cargar las imágenes');
      },
    });
  }

  private loadThumbs(images: TreatmentImage[]): void {
    for (const img of images) {
      this.svc.getImageBlob(img.file_url).subscribe({
        next: blob => {
          const url = URL.createObjectURL(blob);
          this.objectUrls.push(url);
          this.thumbUrls.update(m => ({ ...m, [img.id]: this.sanitizer.bypassSecurityTrustUrl(url) }));
        },
        error: () => {},
      });
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const files = Array.from(input.files);
    input.value = ''; // reset so the same file can be picked again later
    this.uploadFiles(files);
  }

  private async uploadFiles(files: File[]): Promise<void> {
    this.uploading.set(true);
    this.error.set(null);
    let failed = 0;
    for (const file of files) {
      try {
        const { blob, filename } = await compressImage(file);
        await firstValueFrom(this.upload$(blob, filename));
      } catch {
        failed++;
      }
    }
    this.uploading.set(false);
    if (failed > 0) this.error.set(`No se pudieron subir ${failed} imagen(es)`);
    this.reload();
  }

  private upload$(blob: Blob, filename: string) {
    return this.planId != null
      ? this.svc.uploadPlanImage(this.planId, blob, filename)
      : this.svc.uploadImage(this.treatmentId!, blob, filename);
  }

  open(img: TreatmentImage): void { this.active.set(img); }
  close(): void { this.active.set(null); }

  remove(img: TreatmentImage): void {
    if (!confirm('¿Eliminar esta foto? Esta acción no se puede deshacer.')) return;
    this.svc.deleteImage(img.id).subscribe({
      next: () => { this.close(); this.reload(); },
      error: () => this.error.set('No se pudo eliminar la imagen'),
    });
  }

  private revokeAll(): void {
    this.objectUrls.forEach(u => URL.revokeObjectURL(u));
    this.objectUrls = [];
  }
}
