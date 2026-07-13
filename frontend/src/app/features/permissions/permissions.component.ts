import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PermissionService } from '../../core/services/permission.service';
import { ConfirmService } from '../../core/services/confirm.service';
import {
  AppPage, PermissionMatrix, PermissionMatrixResponse, PagePermissions,
} from '../../core/models';

const ROLE_LABELS: Record<string, string> = {
  admin:        'Administrador',
  doctor:       'Médico',
  receptionist: 'Recepcionista',
  assistant:    'Asistente',
  guest:        'Invitado',
};

@Component({
  selector: 'app-permissions',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './permissions.component.html',
  styleUrl: './permissions.component.css',
})
export class PermissionsComponent implements OnInit {
  loading = signal(true);
  saving = signal(false);
  successMsg = signal('');
  errorMsg = signal('');

  pages = signal<AppPage[]>([]);
  roles = signal<string[]>([]);
  matrix = signal<PermissionMatrix>({});

  // New-page form
  showPageForm = signal(false);
  newPage = { key: '', label: '', route: '', description: '' };
  addingPage = signal(false);

  // Edit-page state
  editingPageId = signal<number | null>(null);
  editPage = { label: '', route: '', description: '' };

  roleLabels = ROLE_LABELS;

  constructor(private permissionService: PermissionService, private confirmService: ConfirmService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.permissionService.getMatrix().subscribe({
      next: (res: PermissionMatrixResponse) => {
        this.pages.set(res.pages);
        this.roles.set(res.roles);
        this.matrix.set(this.deepClone(res.matrix));
        this.loading.set(false);
      },
      error: () => {
        this.errorMsg.set('Error al cargar los permisos');
        this.loading.set(false);
      },
    });
  }

  getFlag(role: string, pageKey: string): PagePermissions {
    return this.matrix()[role]?.[pageKey] ?? {
      can_view: false, can_create: false, can_edit: false, can_delete: false,
    };
  }

  toggleView(role: string, pageKey: string): void {
    if (role === 'admin') return; // admin always has access
    const m = this.deepClone(this.matrix());
    if (!m[role]) m[role] = {};
    if (!m[role][pageKey]) m[role][pageKey] = { can_view: false, can_create: false, can_edit: false, can_delete: false };
    const current = m[role][pageKey].can_view;
    m[role][pageKey].can_view = !current;
    // If removing view, also remove sub-permissions
    if (current) {
      m[role][pageKey].can_create = false;
      m[role][pageKey].can_edit = false;
      m[role][pageKey].can_delete = false;
    }
    this.matrix.set(m);
  }

  save(): void {
    this.saving.set(true);
    this.successMsg.set('');
    this.errorMsg.set('');
    this.permissionService.saveMatrix(this.matrix()).subscribe({
      next: () => {
        this.successMsg.set('Permisos guardados correctamente');
        this.saving.set(false);
        // Refresh current user's permissions cache
        this.permissionService.load().subscribe();
        setTimeout(() => this.successMsg.set(''), 3000);
      },
      error: () => {
        this.errorMsg.set('Error al guardar los permisos');
        this.saving.set(false);
      },
    });
  }

  // ── New page form ──────────────────────────────────────────────────────────

  submitNewPage(): void {
    if (!this.newPage.key || !this.newPage.label || !this.newPage.route) return;
    this.addingPage.set(true);
    this.permissionService.createPage({
      key: this.newPage.key,
      label: this.newPage.label,
      route: this.newPage.route,
      description: this.newPage.description,
    }).subscribe({
      next: () => {
        this.newPage = { key: '', label: '', route: '', description: '' };
        this.showPageForm.set(false);
        this.addingPage.set(false);
        this.load();
      },
      error: (err) => {
        this.errorMsg.set(err.error?.error || 'Error al crear la página');
        this.addingPage.set(false);
      },
    });
  }

  // ── Edit page ──────────────────────────────────────────────────────────────

  startEdit(page: AppPage): void {
    this.editingPageId.set(page.id);
    this.editPage = { label: page.label, route: page.route, description: page.description ?? '' };
  }

  cancelEdit(): void { this.editingPageId.set(null); }

  saveEdit(page: AppPage): void {
    this.permissionService.updatePage(page.id, this.editPage).subscribe({
      next: () => { this.editingPageId.set(null); this.load(); },
      error: (err) => this.errorMsg.set(err.error?.error || 'Error al actualizar'),
    });
  }

  async deletePage(page: AppPage): Promise<void> {
    const ok = await this.confirmService.confirm({
      title: 'Eliminar página',
      message: `¿Eliminar la página "${page.label}"? Esta acción no se puede deshacer.`,
      confirmText: 'Eliminar', danger: true,
    });
    if (!ok) return;
    this.permissionService.deletePage(page.id).subscribe({
      next: () => this.load(),
      error: (err) => this.errorMsg.set(err.error?.error || 'Error al eliminar'),
    });
  }

  private deepClone<T>(obj: T): T {
    return JSON.parse(JSON.stringify(obj));
  }
}
