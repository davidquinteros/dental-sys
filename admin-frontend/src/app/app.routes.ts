import { Routes } from '@angular/router';
import { platformAuthGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login/login.component').then(m => m.LoginComponent),
  },
  {
    path: '',
    loadComponent: () => import('./shared/components/layout/layout.component').then(m => m.LayoutComponent),
    canActivate: [platformAuthGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
      },
      {
        path: 'clinics',
        loadComponent: () => import('./features/clinics/clinics-list.component').then(m => m.ClinicsListComponent),
      },
      {
        path: 'clinics/:id',
        loadComponent: () => import('./features/clinics/clinic-detail.component').then(m => m.ClinicDetailComponent),
      },
      {
        path: 'subscription-tiers',
        loadComponent: () => import('./features/subscription-tiers/subscription-tiers.component').then(m => m.SubscriptionTiersComponent),
      },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
