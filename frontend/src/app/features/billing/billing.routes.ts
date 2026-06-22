import { Routes } from '@angular/router';

export const BILLING_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./billing.component').then(m => m.BillingComponent),
  },
  {
    path: 'invoices/new',
    loadComponent: () =>
      import('./invoice-form.component').then(m => m.InvoiceFormComponent),
  },
  {
    path: 'invoices/:id',
    loadComponent: () =>
      import('./invoice-detail.component').then(m => m.InvoiceDetailComponent),
  },
  {
    path: 'payment-plans/new',
    loadComponent: () =>
      import('./payment-plan-form.component').then(m => m.PaymentPlanFormComponent),
  },
  {
    path: 'payment-plans/:id',
    loadComponent: () =>
      import('./payment-plan-detail.component').then(m => m.PaymentPlanDetailComponent),
  },
  {
    path: 'payment-plans/:id/edit',
    loadComponent: () =>
      import('./payment-plan-form.component').then(m => m.PaymentPlanFormComponent),
  },
];
