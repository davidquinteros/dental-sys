import { Routes } from '@angular/router';

export const APPOINTMENTS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./appointments-list.component').then(m => m.AppointmentsListComponent),
  },
  {
    path: 'new',
    loadComponent: () =>
      import('./appointment-form.component').then(m => m.AppointmentFormComponent),
  },
  {
    path: ':id/edit',
    loadComponent: () =>
      import('./appointment-form.component').then(m => m.AppointmentFormComponent),
  },
];
