import { Component, computed, signal, HostListener } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../../core/services/auth.service';
import { PermissionService } from '../../../core/services/permission.service';

interface NavItem {
  label: string;
  icon: string;
  route: string;
}

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, CommonModule],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.css',
})
export class LayoutComponent {
  sidebarCollapsed = signal(false);
  mobileMenuOpen = signal(false);

  constructor(public auth: AuthService, public permissions: PermissionService) {
    this.syncCollapsedForViewport();
  }

  @HostListener('window:resize')
  onResize(): void {
    this.syncCollapsedForViewport();
  }

  private syncCollapsedForViewport(): void {
    if (window.innerWidth <= 1024 && this.sidebarCollapsed()) {
      this.sidebarCollapsed.set(false);
    }
  }

  toggleSidebar(): void {
    this.sidebarCollapsed.update(v => !v);
  }

  toggleMobileMenu(): void {
    this.mobileMenuOpen.update(v => !v);
  }

  closeMobileMenu(): void {
    this.mobileMenuOpen.set(false);
  }

  visibleNavItems = computed(() => {
    const pages = this.permissions.accessiblePages();
    // Dashboard is always first; fall back to static order by sort_order
    return pages.map(p => ({
      label: p.label,
      route: p.route,
      icon: p.icon ?? '',
    }));
  });

  userInitials = computed(() => {
    const user = this.auth.currentUser();
    if (!user) return '?';
    return `${user.first_name[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase();
  });

  roleLabel = computed(() => {
    const roles: Record<string, string> = {
      admin: 'Administrador',
      doctor: 'Médico',
      receptionist: 'Recepcionista',
      assistant: 'Asistente',
    };
    return roles[this.auth.currentUser()?.role ?? ''] ?? '';
  });
}
