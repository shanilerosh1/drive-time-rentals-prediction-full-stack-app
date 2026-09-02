import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ApiService } from '../../core/services/api.service';
import { InspectionType, VehicleWithStats } from '../../core/models/api.models';
import { ModelBannerComponent } from '../../shared/components/model-banner.component';

@Component({
  selector: 'app-inspection-new',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, ModelBannerComponent],
  template: `
    <div class="page narrow">
      <div class="page-header">
        <div>
          <a routerLink="/inspections" class="small back">&larr; Inspections</a>
          <h1>New inspection</h1>
          <p>Open a record, then upload the walk-around photographs on the next screen.</p>
        </div>
      </div>

      <app-model-banner />

      <div class="card">
        <div class="card-body">
          <form [formGroup]="form" (ngSubmit)="submit()">
            <div class="field">
              <label>Inspection type *</label>
              <div class="type-picker">
                <button
                  type="button"
                  class="type-option"
                  [class.selected]="form.controls.inspection_type.value === 'pre_rental'"
                  (click)="form.controls.inspection_type.setValue('pre_rental')"
                >
                  <strong>Pre-rental</strong>
                  <span>Handover baseline, recorded at check-out</span>
                </button>
                <button
                  type="button"
                  class="type-option"
                  [class.selected]="form.controls.inspection_type.value === 'post_rental'"
                  (click)="form.controls.inspection_type.setValue('post_rental')"
                >
                  <strong>Post-rental</strong>
                  <span>Return condition, compared against the baseline</span>
                </button>
              </div>
            </div>

            <div class="field">
              <label for="vehicle">Vehicle *</label>
              <select id="vehicle" formControlName="vehicle_id">
                <option [ngValue]="null" disabled>Select a vehicle…</option>
                <option *ngFor="let v of vehicles()" [ngValue]="v.id">
                  {{ v.registration }} — {{ v.make }} {{ v.model }}
                  <ng-container *ngIf="v.colour"> ({{ v.colour }})</ng-container>
                </option>
              </select>
              <span class="hint" *ngIf="!vehicles().length && !loading()">
                No vehicles yet — <a routerLink="/vehicles">add one first</a>.
              </span>
            </div>

            <div class="two">
              <div class="field">
                <label for="ref">Rental reference</label>
                <input id="ref" type="text" formControlName="rental_ref" placeholder="R-2026-0148" />
                <span class="hint">
                  Pairs the pre- and post-rental checks. Use the same reference on both.
                </span>
              </div>
              <div class="field">
                <label for="odo">Odometer (km)</label>
                <input id="odo" type="number" formControlName="odometer_km" placeholder="42000" />
              </div>
            </div>

            <div class="field">
              <label for="loc">Location</label>
              <input id="loc" type="text" formControlName="location" placeholder="Colombo return bay" />
            </div>

            <div class="field">
              <label for="notes">Notes</label>
              <textarea id="notes" formControlName="notes" placeholder="Anything the photographs will not show…"></textarea>
            </div>

            <div class="alert alert-danger" *ngIf="error()">{{ error() }}</div>

            <div class="row">
              <button class="btn btn-primary" type="submit" [disabled]="form.invalid || saving()">
                <span class="spinner" *ngIf="saving()"></span>
                Create and add photographs
              </button>
              <a routerLink="/inspections" class="btn btn-ghost">Cancel</a>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .narrow { max-width: 700px; }
      .back { display: inline-block; margin-bottom: 6px; }
      form { display: grid; gap: 16px; }
      .two { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
      .type-picker { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
      .type-option {
        display: flex;
        flex-direction: column;
        gap: 3px;
        align-items: flex-start;
        text-align: left;
        padding: 12px 14px;
        border: 1px solid var(--border-strong);
        border-radius: var(--radius-sm);
        background: var(--surface);
        cursor: pointer;
        font: inherit;
        transition: border-color 0.14s ease, background 0.14s ease;
      }
      .type-option:hover { border-color: var(--brand-300); }
      .type-option.selected {
        border-color: var(--brand-500);
        background: var(--brand-050);
        box-shadow: 0 0 0 2px rgba(47, 91, 145, 0.13);
      }
      .type-option strong { font-size: 0.875rem; }
      .type-option span { font-size: 0.72rem; color: var(--ink-500); line-height: 1.35; }
      @media (max-width: 620px) {
        .two, .type-picker { grid-template-columns: 1fr; }
      }
    `,
  ],
})
export class InspectionNewComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly vehicles = signal<VehicleWithStats[]>([]);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    vehicle_id: [null as number | null, Validators.required],
    inspection_type: ['pre_rental' as InspectionType, Validators.required],
    rental_ref: [''],
    odometer_km: [null as number | null],
    location: [''],
    notes: [''],
  });

  ngOnInit(): void {
    this.api.listVehicles(undefined, 200).subscribe({
      next: (page) => {
        this.vehicles.set(page.items);
        this.loading.set(false);

        // Deep-linked from a vehicle page: preselect it.
        const preset = Number(this.route.snapshot.queryParamMap.get('vehicle_id'));
        if (preset && page.items.some((v) => v.id === preset)) {
          this.form.controls.vehicle_id.setValue(preset);
        }
      },
      error: () => {
        this.loading.set(false);
        this.error.set('Could not load the fleet list.');
      },
    });
  }

  submit(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    this.error.set(null);

    const raw = this.form.getRawValue();
    this.api
      .createInspection({
        vehicle_id: raw.vehicle_id!,
        inspection_type: raw.inspection_type,
        rental_ref: raw.rental_ref || null,
        odometer_km: raw.odometer_km ? Number(raw.odometer_km) : null,
        location: raw.location || null,
        notes: raw.notes || null,
      })
      .subscribe({
        next: (inspection) => void this.router.navigate(['/inspections', inspection.id]),
        error: (err) => {
          this.saving.set(false);
          this.error.set(err?.error?.detail ?? 'Could not create the inspection.');
        },
      });
  }
}
