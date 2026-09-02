import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService, InspectionFilters } from '../../core/services/api.service';
import { InspectionStatus, InspectionSummary, InspectionType } from '../../core/models/api.models';
import { DamageChipComponent } from '../../shared/components/damage-chip.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';

@Component({
  selector: 'app-inspection-list',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, DamageChipComponent, StatusBadgeComponent],
  template: `
    <div class="page">
      <div class="page-header">
        <div>
          <h1>Inspections</h1>
          <p>Every recorded pre- and post-rental condition check.</p>
        </div>
        <a routerLink="/inspections/new" class="btn btn-primary">+ New inspection</a>
      </div>

      <div class="card">
        <div class="card-header filters">
          <select [formControl]="typeFilter" aria-label="Filter by type">
            <option value="">All types</option>
            <option value="pre_rental">Pre-rental</option>
            <option value="post_rental">Post-rental</option>
          </select>
          <select [formControl]="statusFilter" aria-label="Filter by status">
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
          <input type="search" [formControl]="rentalRef" placeholder="Rental reference…" class="ref" />
          <div class="spacer"></div>
          <span class="small muted">{{ total() }} record{{ total() === 1 ? '' : 's' }}</span>
        </div>

        <div class="card-body no-pad">
          <div class="loading-row" *ngIf="loading()"><span class="spinner"></span> Loading…</div>

          <div class="empty" *ngIf="!loading() && !rows().length">
            <h3>No inspections match</h3>
            <p class="small">Adjust the filters, or start a new inspection.</p>
          </div>

          <div class="table-wrap" *ngIf="rows().length">
            <table class="data">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Vehicle</th>
                  <th>Type</th>
                  <th>Rental ref</th>
                  <th>Findings</th>
                  <th>Images</th>
                  <th>Inspector</th>
                  <th>Status</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let insp of rows()" class="clickable" (click)="open(insp.id)">
                  <td class="mono">{{ insp.id }}</td>
                  <td>
                    <strong>{{ insp.vehicle?.registration }}</strong>
                    <div class="small muted">{{ insp.vehicle?.make }} {{ insp.vehicle?.model }}</div>
                  </td>
                  <td>
                    <span class="badge" [ngClass]="insp.inspection_type === 'pre_rental' ? 'badge-info' : 'badge-warn'">
                      {{ insp.inspection_type === 'pre_rental' ? 'Pre' : 'Post' }}
                    </span>
                  </td>
                  <td class="small mono">{{ insp.rental_ref || '—' }}</td>
                  <td>
                    <div class="chips">
                      <app-damage-chip *ngFor="let c of insp.damage_classes" [className]="c" />
                      <span class="small muted" *ngIf="!insp.damage_classes.length">Clean</span>
                    </div>
                  </td>
                  <td class="small">{{ insp.image_count }}</td>
                  <td class="small">{{ insp.inspector?.full_name }}</td>
                  <td><app-status-badge [status]="insp.status" /></td>
                  <td class="small muted">{{ insp.created_at | date: 'd MMM y, HH:mm' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card-footer pager" *ngIf="total() > limit">
          <button class="btn btn-sm" [disabled]="offset() === 0" (click)="page(-1)">Previous</button>
          <span class="small muted">
            {{ offset() + 1 }}–{{ min(offset() + limit, total()) }} of {{ total() }}
          </span>
          <button class="btn btn-sm" [disabled]="offset() + limit >= total()" (click)="page(1)">
            Next
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .filters { flex-wrap: wrap; }
      .filters select { width: auto; min-width: 138px; }
      .ref { max-width: 200px; }
      .card-body.no-pad { padding: 0; }
      .chips { display: flex; flex-wrap: wrap; gap: 4px; }
      .loading-row { display: flex; align-items: center; gap: 9px; padding: 26px; color: var(--ink-500); font-size: 0.8125rem; }
      .pager { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    `,
  ],
})
export class InspectionListComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);

  readonly limit = 25;
  readonly rows = signal<InspectionSummary[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly loading = signal(true);

  readonly typeFilter = this.fb.nonNullable.control<'' | InspectionType>('');
  readonly statusFilter = this.fb.nonNullable.control<'' | InspectionStatus>('');
  readonly rentalRef = this.fb.nonNullable.control('');

  ngOnInit(): void {
    this.load();
    for (const control of [this.typeFilter, this.statusFilter, this.rentalRef]) {
      control.valueChanges.subscribe(() => {
        this.offset.set(0);
        this.load();
      });
    }
  }

  load(): void {
    this.loading.set(true);
    const filters: InspectionFilters = { limit: this.limit, offset: this.offset() };
    if (this.typeFilter.value) filters.inspection_type = this.typeFilter.value;
    if (this.statusFilter.value) filters.status = this.statusFilter.value;
    if (this.rentalRef.value.trim()) filters.rental_ref = this.rentalRef.value.trim();

    this.api.listInspections(filters).subscribe({
      next: (page) => {
        this.rows.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  page(direction: 1 | -1): void {
    this.offset.set(Math.max(0, this.offset() + direction * this.limit));
    this.load();
  }

  open(id: number): void {
    void this.router.navigate(['/inspections', id]);
  }

  min(a: number, b: number): number {
    return Math.min(a, b);
  }
}
