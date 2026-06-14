import { inject } from '@angular/core';
import { CanActivateFn, Router, ActivatedRouteSnapshot } from '@angular/router';
import { AuthService } from '../services/auth.service';
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
  const router = inject(Router);
  const requiredRoles: UserRole[] = route.data['roles'] || [];

  if (!authService.isLoggedIn()) {
    router.navigate(['/auth/login']);
    return false;
  }

  if (requiredRoles.length === 0) return true;

  if (authService.hasRole(...requiredRoles)) {
    return true;
  }

  router.navigate(['/dashboard']);
  return false;
};
