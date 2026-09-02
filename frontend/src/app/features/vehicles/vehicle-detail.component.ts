import { CommonModule } from '@angular/common';
import { Component, Input, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ApiService } from '../../core/services/api.service';
import { InspectionSummary, Vehicle } from '../../core/models/api.models';
import { DamageChipComponent } from '../../shared/components/damage-chip.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';

@Component({
  selector: 'app-vehicle-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, DamageChipComponent, StatusBadgeComponent],
  template: `
    <div class="page" *ngIf="vehicle() as v">
      <div class="page-header">
        <div>
          <a routerLink="/vehicles" class="small back">&larr; Fleet</a>
          <h1>{{ v.registration }}</h1>
          <p>
            {{ v.make }} {{ v.model }}<span *ngIf="v.year"> · {{ v.year }}</span>
            <span *ngIf="v.colour"> · {{ v.colour }}</span>
            <span *ngIf="v.body_type"> · {{ v.body_type }}</span>
          </p>
        </div>
        <div class="row">
          <a
            [routerLink]="['/comparison']"
            [queryParams]="{ vehicle_id: v.id }"
            class="btn"
          >Pre / post comparison</a>
          <a
            routerLink="/inspections/new"
            [queryParams]="{ vehicle_id: v.id }"
            class="btn btn-primary"
          >+ New inspection</a>
        </div>
      </div>

      <div class="cols">
        <div class="card">
          <div class="card-header"><h2>Inspection history</h2></div>
          <div class="card-body no-pad">
            <div class="empty" *ngIf="!inspections().length && !loading()">
              <h3>No inspections recorded</h3>
              <p class="small">This vehicle has not been photographed yet.</p>
            </div>
            <div class="loading-row" *ngIf="loading()"><span class="spinner"></span> Loading…</div>
            <div class="table-wrap" *ngIf="inspections().length">
              <table class="data">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Type</th>
                    <th>Rental ref</th>
                    <th>Findings</th>
                    <th>Images</th>
                    <th>Status</th>
                    <th>Date</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr *ngFor="let insp of inspections()">
                    <td class="mono">{{ insp.id }}</td>
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
                    <td><app-status-badge [status]="insp.status" /></td>
                    <td class="small muted">{{ insp.created_at | date: 'd MMM y' }}</td>
                    <td class="right">
                      <a [routerLink]="['/inspections', insp.id]" class="btn btn-sm">Open</a>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="side">
          <div class="card">
            <div class="card-header"><h2>Condition summary</h2></div>
            <div class="card-body">
              <div class="empty small" *ngIf="!currentDamage().length">
                <p>No damage on record from the most recent inspection.</p>
              </div>
              <ng-container *ngIf="currentDamage().length">
                <p class="small muted">
                  From the latest inspection (#{{ latest()?.id }},
                  {{ latest()?.created_at | date: 'd MMM y' }}):
                </p>
                <div class="chips stacked">
                  <app-damage-chip *ngFor="let c of currentDamage()" [className]="c" />
                </div>
              </ng-container>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><h2>Record</h2></div>
            <div class="card-body">
              <dl class="kv">
                <dt>Registration</dt><dd class="mono">{{ v.registration }}</dd>
                <dt>Make</dt><dd>{{ v.make }}</dd>
                <dt>Model</dt><dd>{{ v.model }}</dd>
                <dt>Year</dt><dd>{{ v.year || '—' }}</dd>
                <dt>Colour</dt><dd>{{ v.colour || '—' }}</dd>
                <dt>Body</dt><dd>{{ v.body_type || '—' }}</dd>
                <dt>Added</dt><dd>{{ v.created_at | date: 'd MMM y' }}</dd>
              </dl>
              <p class="small muted notes" *ngIf="v.notes">{{ v.notes }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="page" *ngIf="error()">
      <div class="alert alert-danger">{{ error() }}</div>
    </div>
  `,
  styles: [
    `
      .back { display: inline-block; margin-bottom: 6px; }
      .cols { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 16px; align-items: start; }
      .side { display: grid; gap: 16px; }
      .card-body.no-pad { padding: 0; }
      .card-header h2 { font-size: 0.9375rem; }
      .chips { display: flex; flex-wrap: wrap; gap: 4px; }
      .chips.stacked { margin-top: 8px; }
      .right { text-align: right; }
      .right .btn { text-decoration: none; }
      .loading-row { display: flex; align-items: center; gap: 9px; padding: 26px; color: var(--ink-500); font-size: 0.8125rem; }
      .kv { display: grid; grid-template-columns: auto 1fr; gap: 6px 14px; margin: 0; font-size: 0.8125rem; }
      .kv dt { color: var(--ink-500); font-size: 0.75rem; }
      .kv dd { margin: 0; text-align: right; font-weight: 550; }
      .notes { margin: 12px 0 0; padding-top: 10px; border-top: 1px solid var(--border); }
      .empty { padding: 18px 0; }
      @media (max-width: 940px) { .cols { grid-template-columns: 1fr; } }
    `,
  ],
})
export class VehicleDetailComponent implements OnInit {
  private readonly api = inject(ApiService);

  /** Bound from the route via withComponentInputBinding(). */
  @Input() id!: string;

  readonly vehicle = signal<Vehicle | null>(null);
  readonly inspections = signal<InspectionSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  readonly latest = computed<InspectionSummary | null>(() => this.inspections()[0] ?? null);
  readonly currentDamage = computed(() => this.latest()?.damage_classes ?? []);

  ngOnInit(): void {
    const vehicleId = Number(this.id);
    forkJoin({
      vehicle: this.api.getVehicle(vehicleId),
      inspections: this.api.listInspections({ vehicle_id: vehicleId, limit: 100 }),
    }).subscribe({
      next: ({ vehicle, inspections }) => {
        this.vehicle.set(vehicle);
        this.inspections.set(inspections.items);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.error.set('Could not load this vehicle.');
      },
    });
  }
}
