import { inject } from '@angular/core';
import { CanActivateFn, Router, ActivatedRouteSnapshot } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { PermissionService } from '../services/permission.service';
import { UserRole } from '../models';

export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isLoggedIn()) {
    return true;
  }
  router.navigate(['/auth/login']);
  return false;
};

export const roleGuard: CanActivateFn = (route: ActivatedRouteSnapshot) => {
  const authService = inject(AuthService);
  const permissionService = inject(PermissionService);
  const router = inject(Router);

  if (!authService.isLoggedIn()) {
    router.navigate(['/auth/login']);
    return false;
  }

  // Admin always has full access
  if (authService.isAdmin()) return true;

  // Check dynamic page-key permission first
  const pageKey: string | undefined = route.data['pageKey'];
  if (pageKey) {
    if (permissionService.canView(pageKey)) return true;
    router.navigate(['/dashboard']);
    return false;
  }

  // Fallback: static roles list (used for routes without a pageKey)
  const requiredRoles: UserRole[] = route.data['roles'] || [];
  if (requiredRoles.length === 0) return true;
  if (authService.hasRole(...requiredRoles)) return true;

  router.navigate(['/dashboard']);
  return false;
};
