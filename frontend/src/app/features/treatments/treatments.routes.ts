import { Routes } from '@angular/router';

export const TREATMENTS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./treatments.component').then(m => m.TreatmentsComponent),
  },
  {
    path: 'new',
    loadComponent: () =>
      import('./treatment-form.component').then(m => m.TreatmentFormComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./treatment-detail.component').then(m => m.TreatmentDetailComponent),
  },
  {
    path: 'plans/new',
    loadComponent: () =>
      import('./treatment-plan-form.component').then(m => m.TreatmentPlanFormComponent),
  },
  {
    path: 'plans/:id',
    loadComponent: () =>
      import('./treatment-plan-detail.component').then(m => m.TreatmentPlanDetailComponent),
  },
];
