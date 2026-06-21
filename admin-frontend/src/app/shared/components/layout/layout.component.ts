import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

interface NavItem {
  route: string;
  label: string;
}

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.css',
})
export class LayoutComponent {
  navItems: NavItem[] = [
    { route: '/dashboard', label: 'Dashboard' },
    { route: '/clinics', label: 'Clínicas' },
    { route: '/subscription-tiers', label: 'Planes' },
  ];

  constructor(public auth: AuthService) {}

  userInitials(): string {
    const user = this.auth.currentUser();
    if (!user) return '';
    return `${user.first_name[0] || ''}${user.last_name[0] || ''}`.toUpperCase();
  }
}
