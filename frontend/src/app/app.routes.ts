import { Routes } from '@angular/router';

import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    title: 'Sign in - DriveTime Inspections',
    loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        title: 'Dashboard - DriveTime Inspections',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'vehicles',
        title: 'Fleet - DriveTime Inspections',
        loadComponent: () =>
          import('./features/vehicles/vehicle-list.component').then((m) => m.VehicleListComponent),
      },
      {
        path: 'vehicles/:id',
        title: 'Vehicle - DriveTime Inspections',
        loadComponent: () =>
          import('./features/vehicles/vehicle-detail.component').then(
            (m) => m.VehicleDetailComponent,
          ),
      },
      {
        path: 'inspections',
        title: 'Inspections - DriveTime Inspections',
        loadComponent: () =>
          import('./features/inspections/inspection-list.component').then(
            (m) => m.InspectionListComponent,
          ),
      },
      {
        path: 'inspections/new',
        title: 'New inspection - DriveTime Inspections',
        loadComponent: () =>
          import('./features/inspections/inspection-new.component').then(
            (m) => m.InspectionNewComponent,
          ),
      },
      {
        path: 'inspections/:id',
        title: 'Inspection - DriveTime Inspections',
        loadComponent: () =>
          import('./features/inspections/inspection-detail.component').then(
            (m) => m.InspectionDetailComponent,
          ),
      },
      {
        path: 'model',
        title: 'Model performance - DriveTime Inspections',
        loadComponent: () =>
          import('./features/model/model.component').then((m) => m.ModelComponent),
      },
      {
        path: 'comparison',
        title: 'Pre/post comparison - DriveTime Inspections',
        loadComponent: () =>
          import('./features/comparison/comparison.component').then((m) => m.ComparisonComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
