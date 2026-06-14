import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  {
    path: 'auth',
    loadChildren: () =>
      import('./features/auth/auth.routes').then(m => m.AUTH_ROUTES),
  },
  {
    path: '',
    loadComponent: () =>
      import('./shared/components/layout/layout.component').then(m => m.LayoutComponent),
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
      },
      {
        path: 'users',
        loadComponent: () =>
          import('./features/users/users.component').then(m => m.UsersComponent),
        canActivate: [roleGuard],
        data: { roles: ['admin'] },
      },
      {
        path: 'patients',
        loadChildren: () =>
          import('./features/patients/patients.routes').then(m => m.PATIENTS_ROUTES),
      },
      {
        path: 'appointments',
        loadChildren: () =>
          import('./features/appointments/appointments.routes').then(m => m.APPOINTMENTS_ROUTES),
      },
      {
        path: 'treatments',
        loadChildren: () =>
          import('./features/treatments/treatments.routes').then(m => m.TREATMENTS_ROUTES),
      },
      {
        path: 'billing',
        loadChildren: () =>
          import('./features/billing/billing.routes').then(m => m.BILLING_ROUTES),
        canActivate: [roleGuard],
        data: { roles: ['admin', 'receptionist'] },
      },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: '/dashboard' },
];
