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
    path: 'planes',
    loadComponent: () =>
      import('./features/planes/planes.component').then(m => m.PlanesComponent),
  },
  {
    path: 'treatments/:id/receta',
    loadComponent: () =>
      import('./features/treatments/treatment-receta.component').then(m => m.TreatmentRecetaComponent),
    canActivate: [roleGuard],
    data: { pageKey: 'treatments' },
  },
  {
    path: 'patients/:id/historia/imprimir',
    loadComponent: () =>
      import('./features/patients/patient-medical-history-print.component').then(m => m.PatientMedicalHistoryPrintComponent),
    canActivate: [roleGuard],
    data: { pageKey: 'patients' },
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
        data: { pageKey: 'users', roles: ['admin'] },
      },
      {
        path: 'permissions',
        loadComponent: () =>
          import('./features/permissions/permissions.component').then(m => m.PermissionsComponent),
        canActivate: [roleGuard],
        data: { pageKey: 'permissions', roles: ['admin'] },
      },
      {
        path: 'patients',
        loadChildren: () =>
          import('./features/patients/patients.routes').then(m => m.PATIENTS_ROUTES),
        canActivate: [roleGuard],
        data: { pageKey: 'patients' },
      },
      {
        path: 'appointments',
        loadChildren: () =>
          import('./features/appointments/appointments.routes').then(m => m.APPOINTMENTS_ROUTES),
        canActivate: [roleGuard],
        data: { pageKey: 'appointments' },
      },
      {
        path: 'calendar',
        loadComponent: () =>
          import('./features/calendar/calendar.component').then(m => m.CalendarComponent),
        canActivate: [roleGuard],
        data: { pageKey: 'calendar' },
      },
      {
        path: 'treatments',
        loadChildren: () =>
          import('./features/treatments/treatments.routes').then(m => m.TREATMENTS_ROUTES),
        canActivate: [roleGuard],
        data: { pageKey: 'treatments' },
      },
      {
        path: 'appointment-types',
        loadComponent: () =>
          import('./features/appointment-types/appointment-types.component').then(m => m.AppointmentTypesComponent),
        canActivate: [roleGuard],
        data: { pageKey: 'appointment_types', roles: ['admin'] },
      },
      {
        path: 'consultorios',
        loadComponent: () =>
          import('./features/consultorios/consultorios.component').then(m => m.ConsultoriosComponent),
        canActivate: [roleGuard],
        data: { pageKey: 'consultorios', roles: ['admin'] },
      },
      {
        path: 'billing',
        loadChildren: () =>
          import('./features/billing/billing.routes').then(m => m.BILLING_ROUTES),
        canActivate: [roleGuard],
        data: { pageKey: 'billing', roles: ['admin', 'receptionist'] },
      },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: '/dashboard' },
];
