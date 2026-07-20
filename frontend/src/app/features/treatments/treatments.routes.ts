import { Routes } from '@angular/router';
import { roleGuard } from '../../core/guards/auth.guard';

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
    path: ':id/edit',
    loadComponent: () =>
      import('./treatment-form.component').then(m => m.TreatmentFormComponent),
    canActivate: [roleGuard],
    data: { roles: ['admin', 'doctor'] },
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
  {
    path: 'plans/:id/edit',
    loadComponent: () =>
      import('./treatment-plan-form.component').then(m => m.TreatmentPlanFormComponent),
    canActivate: [roleGuard],
    // Mirrors the backend's medical_staff_required on PUT /treatments/plans/<id>.
    // HEADS UP: `roles` is INERT here, exactly like the one on ':id/edit' above.
    // The parent `treatments` route is componentless (loadChildren), so Angular
    // merges its data into every child — including `pageKey: 'treatments'` — and
    // roleGuard always returns inside its `if (pageKey)` branch without ever
    // reading `roles`. Kept as declared intent; the gates that actually bite are
    // the backend's 403 and the "Editar" button being hidden in
    // treatment-plan-detail. Do NOT fix the guard here — that would newly enable
    // role checks on 5 other routes at once (see FCLI-18).
    data: { roles: ['admin', 'doctor', 'assistant'] },
  },
];
