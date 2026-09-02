import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../core/services/api.service';
import { DamageClassService } from '../../core/services/damage-class.service';
import { DashboardStats } from '../../core/models/api.models';
import { DamageChipComponent } from '../../shared/components/damage-chip.component';
import { ModelBannerComponent } from '../../shared/components/model-banner.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, DamageChipComponent, ModelBannerComponent, StatusBadgeComponent],
  template: `
    <div class="page">
      <div class="page-header">
        <div>
          <h1>Inspection overview</h1>
          <p>Fleet condition activity and model status at a glance.</p>
        </div>
        <a routerLink="/inspections/new" class="btn btn-primary">+ New inspection</a>
      </div>

      <app-model-banner />

      <div class="stats" *ngIf="stats() as s; else loadingTpl">
        <div class="stat card">
          <div class="label">Inspections</div>
          <div class="value">{{ s.total_inspections }}</div>
          <div class="foot">{{ s.inspections_last_7_days }} in the last 7 days</div>
        </div>
        <div class="stat card">
          <div class="label">Fleet vehicles</div>
          <div class="value">{{ s.total_vehicles }}</div>
          <div class="foot">registered for inspection</div>
        </div>
        <div class="stat card">
          <div class="label">Images analysed</div>
          <div class="value">{{ s.images_analysed }}</div>
          <div class="foot">
            {{ s.mean_inference_ms !== null ? (s.mean_inference_ms | number: '1.0-0') + ' ms mean latency' : 'no timings yet' }}
          </div>
        </div>
        <div class="stat card">
          <div class="label">Awaiting completion</div>
          <div class="value">{{ s.draft_inspections }}</div>
          <div class="foot">{{ s.completed_inspections }} completed</div>
        </div>
      </div>

      <ng-template #loadingTpl>
        <div class="stats">
          <div class="skeleton stat-skeleton" *ngFor="let i of [1, 2, 3, 4]"></div>
        </div>
      </ng-template>

      <div class="columns" *ngIf="stats() as s">
        <div class="card">
          <div class="card-header"><h2>Damage detected across the fleet</h2></div>
          <div class="card-body">
            <div class="empty" *ngIf="!classRows().length">
              <h3>Nothing detected yet</h3>
              <p class="small">Run an inspection to populate this breakdown.</p>
            </div>
            <div class="bars" *ngIf="classRows().length">
              <div class="bar-row" *ngFor="let row of classRows()">
                <app-damage-chip [className]="row.name" />
                <div class="bar-track">
                  <div
                    class="bar-fill"
                    [style.width.%]="(row.count / maxClassCount()) * 100"
                    [style.background]="row.colour"
                  ></div>
                </div>
                <span class="count">{{ row.count }}</span>
              </div>
            </div>
            <p class="small muted foot-note" *ngIf="classRows().length">
              Counted as distinct photographs in which the class scored above its threshold.
            </p>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h2>Recent inspections</h2>
            <div class="spacer"></div>
            <a routerLink="/inspections" class="small">View all</a>
          </div>
          <div class="card-body no-pad">
            <div class="empty" *ngIf="!s.recent_inspections.length">
              <h3>No inspections yet</h3>
              <p class="small">Start with a pre-rental walk-around.</p>
            </div>
            <table class="data" *ngIf="s.recent_inspections.length">
              <thead>
                <tr>
                  <th>Vehicle</th>
                  <th>Type</th>
                  <th>Findings</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let insp of s.recent_inspections">
                  <td>
                    <strong>{{ insp.vehicle?.registration }}</strong>
                    <div class="small muted">{{ insp.vehicle?.make }} {{ insp.vehicle?.model }}</div>
                  </td>
                  <td class="small">{{ insp.inspection_type === 'pre_rental' ? 'Pre-rental' : 'Post-rental' }}</td>
                  <td>
                    <div class="chips">
                      <app-damage-chip *ngFor="let c of insp.damage_classes" [className]="c" />
                      <span class="small muted" *ngIf="!insp.damage_classes.length">Clean</span>
                    </div>
                  </td>
                  <td><app-status-badge [status]="insp.status" /></td>
                  <td class="right">
                    <a [routerLink]="['/inspections', insp.id]" class="btn btn-sm">Open</a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="alert alert-danger" *ngIf="error()">{{ error() }}</div>
    </div>
  `,
  styles: [
    `
      .stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 14px;
        margin-bottom: 18px;
      }
      .stat { padding: 16px 18px; }
      .stat .label {
        font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--ink-500); font-weight: 650;
      }
      .stat .value {
        font-size: 1.875rem; font-weight: 700; line-height: 1.2;
        color: var(--brand-900); margin: 4px 0 2px; font-variant-numeric: tabular-nums;
      }
      .stat .foot { font-size: 0.75rem; color: var(--ink-500); }
      .stat-skeleton { height: 96px; }

      .columns { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: 16px; }
      .card-body.no-pad { padding: 0; }
      .card-header h2 { font-size: 0.9375rem; }

      .bars { display: grid; gap: 11px; }
      .bar-row { display: grid; grid-template-columns: 130px 1fr 34px; align-items: center; gap: 10px; }
      .bar-track { height: 8px; background: var(--surface-sunken); border-radius: 4px; overflow: hidden; }
      .bar-fill { height: 100%; border-radius: 4px; transition: width 0.35s ease; }
      .count { font-size: 0.75rem; font-weight: 650; text-align: right; font-variant-numeric: tabular-nums; }
      .foot-note { margin: 14px 0 0; }

      .chips { display: flex; flex-wrap: wrap; gap: 4px; }
      .right { text-align: right; }
      .right .btn { text-decoration: none; }

      @media (max-width: 1000px) {
        .columns { grid-template-columns: 1fr; }
      }
    `,
  ],
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly damageClasses = inject(DamageClassService);

  readonly stats = signal<DashboardStats | null>(null);
  readonly error = signal<string | null>(null);

  readonly classRows = computed(() => {
    const counts = this.stats()?.damage_class_counts ?? {};
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count, colour: this.damageClasses.colour(name) }))
      .sort((a, b) => b.count - a.count);
  });

  readonly maxClassCount = computed(() =>
    Math.max(1, ...this.classRows().map((row) => row.count)),
  );

  ngOnInit(): void {
    this.api.dashboardStats().subscribe({
      next: (stats) => this.stats.set(stats),
      error: () => this.error.set('Could not load dashboard statistics.'),
    });
  }
}
