import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, distinctUntilChanged } from 'rxjs';

import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { VehicleWithStats } from '../../core/models/api.models';

@Component({
  selector: 'app-vehicle-list',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="page">
      <div class="page-header">
        <div>
          <h1>Fleet</h1>
          <p>Vehicles registered for pre- and post-rental inspection.</p>
        </div>
        <button class="btn btn-primary" (click)="showForm.set(!showForm())">
          {{ showForm() ? 'Cancel' : '+ Add vehicle' }}
        </button>
      </div>

      <div class="card add-card" *ngIf="showForm()">
        <div class="card-header"><h2>Add a vehicle</h2></div>
        <div class="card-body">
          <form [formGroup]="form" (ngSubmit)="create()" class="form-grid">
            <div class="field">
              <label for="reg">Registration *</label>
              <input id="reg" type="text" formControlName="registration" placeholder="CBA-1234" />
              <span class="hint">Normalised to upper case; used as the fleet key.</span>
            </div>
            <div class="field">
              <label for="make">Make *</label>
              <input id="make" type="text" formControlName="make" placeholder="Toyota" />
            </div>
            <div class="field">
              <label for="model">Model *</label>
              <input id="model" type="text" formControlName="model" placeholder="Aqua" />
            </div>
            <div class="field">
              <label for="year">Year</label>
              <input id="year" type="number" formControlName="year" placeholder="2019" />
            </div>
            <div class="field">
              <label for="colour">Colour</label>
              <input id="colour" type="text" formControlName="colour" placeholder="Pearl White" />
            </div>
            <div class="field">
              <label for="body">Body type</label>
              <select id="body" formControlName="body_type">
                <option value="">-</option>
                <option>Hatchback</option>
                <option>Saloon</option>
                <option>SUV</option>
                <option>Estate</option>
                <option>Coupe</option>
                <option>Van</option>
              </select>
            </div>
            <div class="actions">
              <div class="alert alert-danger" *ngIf="formError()">{{ formError() }}</div>
              <button class="btn btn-primary" type="submit" [disabled]="form.invalid || saving()">
                <span class="spinner" *ngIf="saving()"></span> Save vehicle
              </button>
            </div>
          </form>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <input
            type="search"
            [formControl]="search"
            placeholder="Search registration, make or model…"
            class="search"
          />
          <div class="spacer"></div>
          <span class="small muted">{{ total() }} vehicle{{ total() === 1 ? '' : 's' }}</span>
        </div>

        <div class="card-body no-pad">
          <div class="empty" *ngIf="!loading() && !vehicles().length">
            <h3>No vehicles found</h3>
            <p class="small">{{ search.value ? 'Try a different search term.' : 'Add your first vehicle to begin.' }}</p>
          </div>

          <div class="loading-row" *ngIf="loading()"><span class="spinner"></span> Loading fleet…</div>

          <div class="table-wrap" *ngIf="vehicles().length">
            <table class="data">
              <thead>
                <tr>
                  <th>Registration</th>
                  <th>Vehicle</th>
                  <th>Colour</th>
                  <th>Inspections</th>
                  <th>Last inspected</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr
                  *ngFor="let v of vehicles()"
                  class="clickable"
                  (click)="open(v.id)"
                >
                  <td><strong>{{ v.registration }}</strong></td>
                  <td>
                    {{ v.make }} {{ v.model }}
                    <span class="muted small" *ngIf="v.year"> · {{ v.year }}</span>
                  </td>
                  <td class="small">{{ v.colour || '—' }}</td>
                  <td>
                    <span class="badge badge-neutral">{{ v.inspection_count }}</span>
                  </td>
                  <td class="small muted">
                    {{ v.last_inspected_at ? (v.last_inspected_at | date: 'd MMM y, HH:mm') : 'Never' }}
                  </td>
                  <td class="right">
                    <a [routerLink]="['/vehicles', v.id]" class="btn btn-sm" (click)="$event.stopPropagation()">
                      Open
                    </a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .add-card { margin-bottom: 16px; }
      .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
      .actions { grid-column: 1 / -1; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
      .actions .alert { flex: 1; min-width: 200px; }
      .search { max-width: 320px; }
      .card-body.no-pad { padding: 0; }
      .right { text-align: right; }
      .right .btn { text-decoration: none; }
      .loading-row { display: flex; align-items: center; gap: 9px; padding: 26px; color: var(--ink-500); font-size: 0.8125rem; }
    `,
  ],
})
export class VehicleListComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);

  readonly vehicles = signal<VehicleWithStats[]>([]);
  readonly total = signal(0);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly showForm = signal(false);
  readonly formError = signal<string | null>(null);

  readonly search = this.fb.nonNullable.control('');

  readonly form = this.fb.nonNullable.group({
    registration: ['', Validators.required],
    make: ['', Validators.required],
    model: ['', Validators.required],
    year: [null as number | null],
    colour: [''],
    body_type: [''],
  });

  ngOnInit(): void {
    this.load();
    this.search.valueChanges
      .pipe(debounceTime(280), distinctUntilChanged())
      .subscribe(() => this.load());
  }

  load(): void {
    this.loading.set(true);
    this.api.listVehicles(this.search.value).subscribe({
      next: (page) => {
        this.vehicles.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  create(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    this.formError.set(null);

    const raw = this.form.getRawValue();
    // Send absent optional fields as null rather than '' so the API's
    // max-length validators are not tripped by empty strings.
    this.api
      .createVehicle({
        registration: raw.registration,
        make: raw.make,
        model: raw.model,
        year: raw.year ? Number(raw.year) : null,
        colour: raw.colour || null,
        body_type: raw.body_type || null,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.showForm.set(false);
          this.form.reset();
          this.load();
        },
        error: (err) => {
          this.saving.set(false);
          this.formError.set(err?.error?.detail ?? 'Could not save the vehicle.');
        },
      });
  }

  open(id: number): void {
    void this.router.navigate(['/vehicles', id]);
  }
}
