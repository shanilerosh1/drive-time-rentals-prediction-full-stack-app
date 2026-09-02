import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ApiService, ComparisonQuery } from '../../core/services/api.service';
import { DownloadService } from '../../core/services/download.service';
import { Comparison, DamageOutcome, Inspection, VehicleWithStats } from '../../core/models/api.models';
import { AuthImageComponent } from '../../shared/components/auth-image.component';
import { DamageChipComponent } from '../../shared/components/damage-chip.component';

@Component({
  selector: 'app-comparison',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, AuthImageComponent, DamageChipComponent],
  template: `
    <div class="page">
      <div class="page-header">
        <div>
          <h1>Pre / post comparison</h1>
          <p>Which damage arose during the rental, and which was already there at handover.</p>
        </div>
        <button
          class="btn btn-primary"
          (click)="downloadReport()"
          [disabled]="!comparison() || downloading()"
        >
          <span class="spinner" *ngIf="downloading()"></span> Export comparison PDF
        </button>
      </div>

      <div class="card selector">
        <div class="card-body">
          <div class="selector-grid">
            <div class="field">
              <label for="vehicle">Vehicle</label>
              <select id="vehicle" [formControl]="vehicleControl">
                <option [ngValue]="null" disabled>Select a vehicle…</option>
                <option *ngFor="let v of vehicles()" [ngValue]="v.id">
                  {{ v.registration }} — {{ v.make }} {{ v.model }}
                </option>
              </select>
            </div>
            <div class="field">
              <label for="ref">Rental reference (optional)</label>
              <input id="ref" type="text" [formControl]="refControl" placeholder="Leave blank for the latest pair" />
            </div>
            <button class="btn" (click)="load()" [disabled]="!vehicleControl.value || loading()">
              <span class="spinner" *ngIf="loading()"></span> Compare
            </button>
          </div>
        </div>
      </div>

      <div class="empty card" *ngIf="!comparison() && !loading()">
        <h3>Select a vehicle to compare</h3>
        <p class="small">
          The latest pre-rental and post-rental inspection are matched automatically, or pinned
          to a rental reference if you supply one.
        </p>
      </div>

      <ng-container *ngIf="comparison() as c">
        <div class="alert" [ngClass]="c.uses_real_model ? 'alert-info' : 'alert-warn'" *ngIf="!c.uses_real_model">
          <span aria-hidden="true">⚠</span>
          <div>
            <strong>Placeholder findings.</strong> These results come from the stub predictor, so
            the delta below demonstrates the comparison logic rather than real vehicle condition.
          </div>
        </div>

        <div class="alert alert-info" *ngIf="c.note">{{ c.note }}</div>

        <!-- Verdict -->
        <div class="verdict card" [class.has-new]="c.new_damage_classes.length">
          <div class="card-body">
            <div class="verdict-main">
              <div class="verdict-icon" aria-hidden="true">
                {{ c.new_damage_classes.length ? '⚠' : '✓' }}
              </div>
              <div>
                <h2>
                  {{ c.new_damage_classes.length
                    ? c.new_damage_classes.length + ' new damage class' + (c.new_damage_classes.length === 1 ? '' : 'es') + ' on return'
                    : 'No new damage detected' }}
                </h2>
                <p class="small muted">
                  {{ c.vehicle.registration }} · {{ c.vehicle.make }} {{ c.vehicle.model }}
                  <span *ngIf="c.rental_ref"> · rental {{ c.rental_ref }}</span>
                </p>
                <div class="chips" *ngIf="c.new_damage_classes.length">
                  <app-damage-chip *ngFor="let cls of c.new_damage_classes" [className]="cls" />
                </div>
              </div>
            </div>
            <div class="verdict-side">
              <div>
                <div class="label">Pre-existing</div>
                <div class="chips">
                  <app-damage-chip *ngFor="let cls of c.pre_existing_classes" [className]="cls" />
                  <span class="small muted" *ngIf="!c.pre_existing_classes.length">None</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Delta table -->
        <div class="card">
          <div class="card-header"><h2>Damage delta</h2></div>
          <div class="card-body no-pad">
            <div class="empty" *ngIf="!c.rows.length">
              <p class="small">No damage was detected in either inspection.</p>
            </div>
            <div class="table-wrap" *ngIf="c.rows.length">
              <table class="data">
                <thead>
                  <tr>
                    <th>Damage class</th>
                    <th>Outcome</th>
                    <th>At handover</th>
                    <th>On return</th>
                  </tr>
                </thead>
                <tbody>
                  <tr *ngFor="let row of c.rows" [ngClass]="'row-' + row.outcome">
                    <td><app-damage-chip [className]="row.class_name" [severity]="row.severity_hint" /></td>
                    <td>
                      <span class="badge" [ngClass]="outcomeClass(row.outcome)">
                        {{ outcomeLabel(row.outcome) }}
                      </span>
                    </td>
                    <td class="score">
                      {{ row.pre_confidence !== null ? (row.pre_confidence * 100 | number: '1.0-1') + '%' : 'not detected' }}
                    </td>
                    <td class="score">
                      {{ row.post_confidence !== null ? (row.post_confidence * 100 | number: '1.0-1') + '%' : 'not detected' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="card-footer">
            <p class="small muted">
              A class counts as new only when it was below threshold in every pre-rental photograph
              and above threshold in at least one post-rental photograph. Absence of a detection is
              not proof of absence of damage.
            </p>
          </div>
        </div>

        <!-- Side-by-side evidence -->
        <div class="sides">
          <div class="card side">
            <div class="card-header">
              <h2>At handover</h2>
              <div class="spacer"></div>
              <a *ngIf="c.pre_inspection" [routerLink]="['/inspections', c.pre_inspection.id]" class="small">
                Inspection #{{ c.pre_inspection.id }}
              </a>
            </div>
            <div class="card-body">
              <ng-container *ngIf="c.pre_inspection; else noPre">
                <p class="small muted meta">
                  {{ c.pre_inspection.created_at | date: 'd MMM y, HH:mm' }} ·
                  {{ c.pre_inspection.inspector?.full_name }} ·
                  {{ c.pre_inspection.odometer_km ? (c.pre_inspection.odometer_km | number) + ' km' : 'no odometer' }}
                </p>
                <div class="thumbs">
                  <div class="thumb" *ngFor="let img of c.pre_inspection.images">
                    <app-auth-image [path]="img.thumbnail_url" [alt]="'Pre-rental photograph'" />
                  </div>
                  <p class="small muted" *ngIf="!c.pre_inspection.images.length">No photographs.</p>
                </div>
              </ng-container>
              <ng-template #noPre>
                <p class="small muted">No pre-rental inspection on record.</p>
              </ng-template>
            </div>
          </div>

          <div class="card side">
            <div class="card-header">
              <h2>On return</h2>
              <div class="spacer"></div>
              <a *ngIf="c.post_inspection" [routerLink]="['/inspections', c.post_inspection.id]" class="small">
                Inspection #{{ c.post_inspection.id }}
              </a>
            </div>
            <div class="card-body">
              <ng-container *ngIf="c.post_inspection; else noPost">
                <p class="small muted meta">
                  {{ c.post_inspection.created_at | date: 'd MMM y, HH:mm' }} ·
                  {{ c.post_inspection.inspector?.full_name }} ·
                  {{ c.post_inspection.odometer_km ? (c.post_inspection.odometer_km | number) + ' km' : 'no odometer' }}
                </p>
                <div class="thumbs">
                  <div class="thumb" *ngFor="let img of c.post_inspection.images">
                    <app-auth-image [path]="img.thumbnail_url" [alt]="'Post-rental photograph'" />
                  </div>
                  <p class="small muted" *ngIf="!c.post_inspection.images.length">No photographs.</p>
                </div>
              </ng-container>
              <ng-template #noPost>
                <p class="small muted">No post-rental inspection on record.</p>
              </ng-template>
            </div>
          </div>
        </div>
      </ng-container>

      <div class="alert alert-danger" *ngIf="error()">{{ error() }}</div>
    </div>
  `,
  styles: [
    `
      .selector { margin-bottom: 16px; }
      .selector-grid { display: grid; grid-template-columns: 1fr 1fr auto; gap: 14px; align-items: end; }

      .verdict { margin: 16px 0; border-left: 3px solid var(--ok-600); }
      .verdict.has-new { border-left-color: var(--danger-600); }
      .verdict .card-body { display: flex; justify-content: space-between; gap: 28px; flex-wrap: wrap; }
      .verdict-main { display: flex; gap: 14px; align-items: flex-start; }
      .verdict-icon {
        width: 38px; height: 38px; flex: none; border-radius: 50%;
        display: grid; place-items: center; font-size: 1.05rem;
        background: var(--ok-050); color: var(--ok-600);
      }
      .verdict.has-new .verdict-icon { background: var(--danger-050); color: var(--danger-600); }
      .verdict h2 { font-size: 1.0625rem; margin-bottom: 2px; }
      .chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
      .label {
        font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--ink-500); font-weight: 650;
      }
      .verdict-side .chips { margin-top: 6px; }

      .card-body.no-pad { padding: 0; }
      .card-header h2 { font-size: 0.9375rem; }
      .score { font-variant-numeric: tabular-nums; font-size: 0.8125rem; }
      tr.row-new { background: #fdf2f2; }
      tr.row-new:hover { background: #fbe9e9; }

      .sides { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
      .meta { margin: 0 0 12px; }
      .thumbs { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: 8px; }
      .thumb {
        aspect-ratio: 4 / 3;
        border-radius: var(--radius-sm);
        overflow: hidden;
        border: 1px solid var(--border);
      }

      @media (max-width: 900px) {
        .selector-grid, .sides { grid-template-columns: 1fr; }
      }
    `,
  ],
})
export class ComparisonComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly downloads = inject(DownloadService);

  readonly vehicles = signal<VehicleWithStats[]>([]);
  readonly comparison = signal<Comparison | null>(null);
  readonly loading = signal(false);
  readonly downloading = signal(false);
  readonly error = signal<string | null>(null);

  readonly vehicleControl = this.fb.control<number | null>(null);
  readonly refControl = this.fb.nonNullable.control('');

  ngOnInit(): void {
    this.api.listVehicles(undefined, 200).subscribe({
      next: (page) => {
        this.vehicles.set(page.items);

        // Deep-linked from a vehicle or inspection page: run it immediately.
        const params = this.route.snapshot.queryParamMap;
        const vehicleId = Number(params.get('vehicle_id'));
        if (vehicleId && page.items.some((v) => v.id === vehicleId)) {
          this.vehicleControl.setValue(vehicleId);
          this.refControl.setValue(params.get('rental_ref') ?? '');
          this.load();
        }
      },
      error: () => this.error.set('Could not load the fleet list.'),
    });
  }

  private query(): ComparisonQuery {
    const query: ComparisonQuery = { vehicle_id: this.vehicleControl.value ?? undefined };
    if (this.refControl.value.trim()) query.rental_ref = this.refControl.value.trim();
    return query;
  }

  load(): void {
    if (!this.vehicleControl.value) return;
    this.loading.set(true);
    this.error.set(null);

    this.api.compare(this.query()).subscribe({
      next: (comparison) => {
        this.comparison.set(comparison);
        this.loading.set(false);
      },
      error: (err) => {
        this.loading.set(false);
        this.comparison.set(null);
        this.error.set(err?.error?.detail ?? 'Could not build the comparison.');
      },
    });
  }

  downloadReport(): void {
    const comparison = this.comparison();
    if (!comparison) return;

    this.downloading.set(true);
    this.api.comparisonReport(this.query()).subscribe({
      next: (blob) => {
        this.downloads.save(blob, `comparison-${comparison.vehicle.registration}.pdf`);
        this.downloading.set(false);
      },
      error: () => {
        this.downloading.set(false);
        this.error.set('Could not generate the comparison report.');
      },
    });
  }

  outcomeLabel(outcome: DamageOutcome): string {
    return {
      new: 'New this rental',
      pre_existing: 'Pre-existing',
      resolved: 'Not detected on return',
    }[outcome];
  }

  outcomeClass(outcome: DamageOutcome): string {
    return {
      new: 'badge-danger',
      pre_existing: 'badge-neutral',
      resolved: 'badge-ok',
    }[outcome];
  }
}
