import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { ApiService } from '../../core/services/api.service';
import { DamageClassService } from '../../core/services/damage-class.service';
import { ClassMetrics, ModelEvaluation, ModelInfo } from '../../core/models/api.models';
import { DamageChipComponent } from '../../shared/components/damage-chip.component';

interface ClassRow extends ClassMetrics {
  name: string;
  threshold: number;
}

@Component({
  selector: 'app-model',
  standalone: true,
  imports: [CommonModule, DamageChipComponent],
  template: `
    <div class="page">
      <div class="page-header">
        <div>
          <h1>Model performance</h1>
          <p>
            Measured by running the deployed model over the held-out CarDD test split &mdash;
            images it never saw during training.
          </p>
        </div>
        <button class="btn" (click)="load()" [disabled]="loading()">
          <span class="spinner" *ngIf="loading()"></span> Refresh
        </button>
      </div>

      <!-- Which model is answering -->
      <div class="card" *ngIf="info() as m">
        <div class="card-body">
          <div class="provenance">
            <div>
              <div class="label">Loaded model</div>
              <div class="value">{{ m.model_name }}</div>
              <div class="small muted">backend: {{ m.backend }} &middot; version {{ m.model_version }}</div>
            </div>
            <div>
              <div class="label">Status</div>
              <span class="badge" [ngClass]="m.is_real ? 'badge-ok' : 'badge-warn'">
                {{ m.is_real ? 'Trained weights loaded' : 'Placeholder predictor' }}
              </span>
            </div>
            <div *ngIf="m.device">
              <div class="label">Device</div>
              <div class="value small-value">{{ m.device }}</div>
            </div>
            <div>
              <div class="label">Localisation</div>
              <div class="value small-value">
                {{ m.produces_bounding_boxes ? 'Bounding boxes' : 'Image-level classes' }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- No evaluation yet -->
      <div class="card empty-card" *ngIf="!evaluation() && !loading()">
        <div class="card-body">
          <h3>No evaluation report yet</h3>
          <p class="small muted">{{ error() || 'Run the verification harness to produce one.' }}</p>
          <pre class="cmd">cd backend
.venv/bin/python training/download_dataset.py
.venv/bin/python training/evaluate.py --data-root data/CarDD_COCO</pre>
          <p class="small muted">
            It scores the test split through the same code path the API uses to answer a
            request, then writes <code>models/evaluation.json</code>, which this page reads.
          </p>
        </div>
      </div>

      <ng-container *ngIf="evaluation() as ev">
        <!-- Headline numbers -->
        <div class="stats">
          <div class="stat card">
            <div class="label">Macro F1</div>
            <div class="value">{{ ev.macro.f1 | number: '1.3-3' }}</div>
            <div class="foot">mean across the six classes</div>
          </div>
          <div class="stat card">
            <div class="label">Macro ROC-AUC</div>
            <div class="value">{{ ev.macro.roc_auc | number: '1.3-3' }}</div>
            <div class="foot">threshold-independent ranking</div>
          </div>
          <div class="stat card" *ngIf="ev.clean_images; else noCleanTpl">
            <div class="label">Damaged vs clean</div>
            <div class="value">{{ ev.any_damage_accuracy * 100 | number: '1.1-1' }}%</div>
            <div class="foot">over {{ ev.clean_images }} clean cars + damaged</div>
          </div>
          <ng-template #noCleanTpl>
            <div class="stat card warn-stat">
              <div class="label">Damage found when present</div>
              <div class="value">{{ ev.any_damage_accuracy * 100 | number: '1.1-1' }}%</div>
              <div class="foot">recall only &mdash; no clean cars tested</div>
            </div>
          </ng-template>
          <div class="stat card">
            <div class="label">Exact match</div>
            <div class="value">{{ ev.exact_match_ratio * 100 | number: '1.1-1' }}%</div>
            <div class="foot">all six classes simultaneously right</div>
          </div>
          <div
            class="stat card"
            *ngIf="ev.false_alarm_rate !== undefined"
            [class.bad-stat]="ev.false_alarm_rate > 0.15"
            [class.good-stat]="ev.false_alarm_rate <= 0.15"
          >
            <div class="label">False alarms</div>
            <div class="value">{{ ev.false_alarm_rate * 100 | number: '1.1-1' }}%</div>
            <div class="foot">
              damage reported on {{ ev.false_alarms }} of {{ ev.clean_images }} undamaged cars
            </div>
          </div>
        </div>

        <div class="alert alert-warn" *ngIf="ev.clean_images === undefined">
          <span aria-hidden="true">⚠</span>
          <div>
            <strong>No undamaged cars in this test set.</strong>
            Every image scored here contains damage, so these figures cannot tell you how
            often the model reports damage on a <em>clean</em> car &mdash; the failure that
            matters most in a dispute. Add undamaged photographs
            (<code class="mono">training/extract_negatives.py</code>) and re-run the
            evaluation to measure it.
          </div>
        </div>

        <div class="alert alert-info meta-line">
          Evaluated on <strong>{{ ev.images }}</strong> held-out {{ ev.split }} images
          &middot; {{ ev.model_name }} ({{ ev.backend }})
          &middot; latency {{ ev.latency_ms.mean | number: '1.0-0' }} ms mean,
          {{ ev.latency_ms.p95 | number: '1.0-0' }} ms p95
          &middot; {{ ev.evaluated_at }}
        </div>

        <!-- Per-class breakdown -->
        <div class="card">
          <div class="card-header"><h2>Per-class results</h2></div>
          <div class="card-body no-pad">
            <div class="table-wrap">
              <table class="data">
                <thead>
                  <tr>
                    <th>Class</th>
                    <th class="num">Threshold</th>
                    <th class="num">Support</th>
                    <th class="num">Precision</th>
                    <th class="num">Recall</th>
                    <th class="num">F1</th>
                    <th class="num">AP</th>
                    <th class="num">ROC-AUC</th>
                    <th class="num">TP / FP / FN</th>
                  </tr>
                </thead>
                <tbody>
                  <tr *ngFor="let row of classRows()">
                    <td><app-damage-chip [className]="row.name" /></td>
                    <td class="num mono">{{ row.threshold | number: '1.3-3' }}</td>
                    <td class="num">{{ row.support }}</td>
                    <td class="num">{{ row.precision | number: '1.3-3' }}</td>
                    <td class="num">
                      <div class="bar-cell">
                        <div class="bar"><div class="fill" [style.width.%]="row.recall * 100"></div></div>
                        {{ row.recall | number: '1.3-3' }}
                      </div>
                    </td>
                    <td class="num strong">{{ row.f1 | number: '1.3-3' }}</td>
                    <td class="num">{{ row.average_precision ? (row.average_precision | number: '1.3-3') : '—' }}</td>
                    <td class="num">{{ row.roc_auc ? (row.roc_auc | number: '1.3-3') : '—' }}</td>
                    <td class="num mono small">{{ row.tp }} / {{ row.fp }} / {{ row.fn }}</td>
                  </tr>
                </tbody>
                <tfoot>
                  <tr class="totals">
                    <td><strong>Macro average</strong></td>
                    <td></td>
                    <td></td>
                    <td class="num">{{ ev.macro.precision | number: '1.3-3' }}</td>
                    <td class="num">{{ ev.macro.recall | number: '1.3-3' }}</td>
                    <td class="num strong">{{ ev.macro.f1 | number: '1.3-3' }}</td>
                    <td class="num">{{ ev.macro.average_precision | number: '1.3-3' }}</td>
                    <td class="num">{{ ev.macro.roc_auc | number: '1.3-3' }}</td>
                    <td></td>
                  </tr>
                  <tr class="totals">
                    <td><strong>Micro average</strong></td>
                    <td></td>
                    <td></td>
                    <td class="num">{{ ev.micro.precision | number: '1.3-3' }}</td>
                    <td class="num">{{ ev.micro.recall | number: '1.3-3' }}</td>
                    <td class="num strong">{{ ev.micro.f1 | number: '1.3-3' }}</td>
                    <td colspan="3"></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
          <div class="card-footer">
            <p class="small muted">
              <strong>Precision</strong> is how often a reported detection is real &mdash; low
              precision means false accusations. <strong>Recall</strong> is how much of the real
              damage is found &mdash; low recall means missed damage. For a dispute-support tool
              precision matters more, which is why each class uses its own F1-optimised threshold
              rather than a flat 0.5.
            </p>
          </div>
        </div>

        <!-- Spot check -->
        <div class="card" *ngIf="examples().length">
          <div class="card-header">
            <h2>Spot check</h2>
            <div class="spacer"></div>
            <div class="toggle">
              <button class="btn btn-sm" [class.on]="filter() === 'all'" (click)="filter.set('all')">
                All
              </button>
              <button class="btn btn-sm" [class.on]="filter() === 'wrong'" (click)="filter.set('wrong')">
                Mistakes only ({{ wrongCount() }})
              </button>
            </div>
          </div>
          <div class="card-body no-pad">
            <div class="table-wrap">
              <table class="data">
                <thead>
                  <tr>
                    <th>Image</th>
                    <th>Ground truth (CarDD)</th>
                    <th>Model said</th>
                    <th class="num">Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  <tr *ngFor="let ex of visibleExamples()">
                    <td class="mono small">{{ ex.file_name }}</td>
                    <td>
                      <div class="chips">
                        <app-damage-chip *ngFor="let c of ex.truth" [className]="c" />
                        <span class="small muted" *ngIf="!ex.truth.length">clean</span>
                      </div>
                    </td>
                    <td>
                      <div class="chips">
                        <app-damage-chip *ngFor="let c of ex.predicted" [className]="c" />
                        <span class="small muted" *ngIf="!ex.predicted.length">clean</span>
                      </div>
                    </td>
                    <td class="num">
                      <span class="badge" [ngClass]="ex.correct ? 'badge-ok' : 'badge-danger'">
                        {{ ex.correct ? 'exact' : 'differs' }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="card-footer">
            <p class="small muted">
              Showing {{ visibleExamples().length }} of {{ examples().length }} recorded
              examples. "Differs" counts any disagreement across all six classes at once, so a
              row can differ on one class while being right about the other five.
            </p>
          </div>
        </div>
      </ng-container>
    </div>
  `,
  styles: [
    `
      .provenance { display: flex; gap: 40px; flex-wrap: wrap; }
      .label {
        font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--ink-500); font-weight: 650; margin-bottom: 4px;
      }
      .value { font-size: 1rem; font-weight: 650; color: var(--brand-900); }
      .small-value { font-size: 0.8125rem; }

      .stats {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 14px; margin: 16px 0;
      }
      .stat { padding: 16px 18px; }
      .stat .value {
        font-size: 1.75rem; font-weight: 700; line-height: 1.2;
        margin: 3px 0 2px; font-variant-numeric: tabular-nums;
      }
      .stat .foot { font-size: 0.72rem; color: var(--ink-500); }
      .bad-stat { border-color: #e9c4c1; background: var(--danger-050); }
      .bad-stat .value { color: var(--danger-600); }
      .good-stat { border-color: #bfe3d2; background: var(--ok-050); }
      .good-stat .value { color: var(--ok-600); }
      .warn-stat { border-color: #f0d9ae; background: var(--warn-050); }

      .meta-line { margin-bottom: 16px; }
      .card { margin-bottom: 16px; }
      .card-body.no-pad { padding: 0; }
      .card-header h2 { font-size: 0.9375rem; }

      .num { text-align: right; font-variant-numeric: tabular-nums; }
      .num.strong { font-weight: 700; }
      table.data tfoot td {
        border-top: 1.5px solid var(--border-strong);
        background: var(--surface-alt); padding: 9px 12px;
      }
      .bar-cell { display: flex; align-items: center; gap: 7px; justify-content: flex-end; }
      .bar {
        width: 46px; height: 5px; background: var(--surface-sunken);
        border-radius: 3px; overflow: hidden;
      }
      .fill { height: 100%; background: var(--brand-500); }

      .chips { display: flex; flex-wrap: wrap; gap: 4px; }
      .toggle { display: flex; gap: 5px; }
      .toggle .btn.on { background: var(--brand-700); color: #fff; border-color: var(--brand-700); }

      .empty-card h3 { margin-bottom: 6px; }
      .cmd {
        background: var(--surface-sunken); border: 1px solid var(--border);
        border-radius: var(--radius-sm); padding: 11px 13px; font-size: 0.75rem;
        font-family: var(--mono); overflow-x: auto; margin: 12px 0;
      }
    `,
  ],
})
export class ModelComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly damageClasses = inject(DamageClassService);

  readonly info = signal<ModelInfo | null>(null);
  readonly evaluation = signal<ModelEvaluation | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly filter = signal<'all' | 'wrong'>('all');

  readonly classRows = computed<ClassRow[]>(() => {
    const ev = this.evaluation();
    if (!ev) return [];
    // Preserve the taxonomy's own order rather than object key order.
    const order = this.damageClasses.classes().map((c) => c.name);
    const names = order.length ? order : Object.keys(ev.per_class);
    return names
      .filter((name) => ev.per_class[name])
      .map((name) => ({
        ...ev.per_class[name],
        name,
        threshold: ev.thresholds?.[name] ?? 0.5,
      }));
  });

  readonly examples = computed(() => this.evaluation()?.examples ?? []);
  readonly wrongCount = computed(() => this.examples().filter((e) => !e.correct).length);
  readonly visibleExamples = computed(() => {
    const rows = this.filter() === 'wrong' ? this.examples().filter((e) => !e.correct) : this.examples();
    return rows.slice(0, 60);
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      info: this.api.modelInfo().pipe(catchError(() => of(null))),
      // A missing report is the normal state before the harness has been run,
      // so a 404 must not be surfaced as a failure.
      evaluation: this.api.modelEvaluation().pipe(
        catchError((err) => {
          this.error.set(err?.error?.detail ?? null);
          return of(null);
        }),
      ),
    }).subscribe(({ info, evaluation }) => {
      this.info.set(info);
      this.evaluation.set(evaluation);
      this.loading.set(false);
    });
  }
}
