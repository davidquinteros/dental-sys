import { Component, computed, signal, HostListener, OnInit } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { AuthService } from '../../../core/services/auth.service';
import { PermissionService } from '../../../core/services/permission.service';
import { ClinicService } from '../../../core/services/api.service';

interface NavItem {
  key: string;
  label: string;
  route: string;
}

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, CommonModule],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.css',
})
export class LayoutComponent implements OnInit {
  sidebarCollapsed = signal(false);
  mobileMenuOpen = signal(false);

  constructor(
    public auth: AuthService,
    public permissions: PermissionService,
    private clinicService: ClinicService,
    private sanitizer: DomSanitizer,
  ) {
    this.syncCollapsedForViewport();
  }

  ngOnInit(): void {
    // Populates the shared main-logo signal used by the sidebar brand; a 404
    // (no logo yet) leaves it null so the default tooth icon shows instead.
    this.clinicService.refreshMainLogo();
  }

  /** Main logo for the sidebar brand (blob object URL → SafeUrl), or null. */
  mainLogo = computed<SafeUrl | null>(() => {
    const url = this.clinicService.mainLogoUrl();
    return url ? this.sanitizer.bypassSecurityTrustUrl(url) : null;
  });

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

  visibleNavItems = computed<NavItem[]>(() => {
    const pages = this.permissions.accessiblePages();
    // Dashboard is always first; fall back to static order by sort_order.
    // The icon is resolved in the template by page key (see the @switch in
    // layout.component.html) — the DB icon string can't be innerHTML-bound.
    // clinic_profile is a real Page (for roleGuard) but is reached only via the
    // sidebar brand (FCLI-23), so it must not also appear as a nav row.
    return pages
      .filter(p => p.key !== 'clinic_profile')
      .map(p => ({
        key: p.key,
        label: p.label,
        route: p.route,
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
