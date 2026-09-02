import { CommonModule } from '@angular/common';
import { Component, Input, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { DamageClassService } from '../../core/services/damage-class.service';
import { DownloadService } from '../../core/services/download.service';
import { CaptureAngle, Inspection, InspectionImage } from '../../core/models/api.models';
import { AnnotatedImageComponent } from '../../shared/components/annotated-image.component';
import { ConfidenceBarComponent } from '../../shared/components/confidence-bar.component';
import { DamageChipComponent } from '../../shared/components/damage-chip.component';
import { ModelBannerComponent } from '../../shared/components/model-banner.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';

const CAPTURE_ANGLES: { value: CaptureAngle; label: string }[] = [
  { value: 'front', label: 'Front' },
  { value: 'front_left', label: 'Front left' },
  { value: 'front_right', label: 'Front right' },
  { value: 'left', label: 'Left side' },
  { value: 'right', label: 'Right side' },
  { value: 'rear', label: 'Rear' },
  { value: 'rear_left', label: 'Rear left' },
  { value: 'rear_right', label: 'Rear right' },
  { value: 'roof', label: 'Roof' },
  { value: 'detail', label: 'Close-up detail' },
  { value: 'other', label: 'Other' },
];

@Component({
  selector: 'app-inspection-detail',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    AnnotatedImageComponent,
    ConfidenceBarComponent,
    DamageChipComponent,
    ModelBannerComponent,
    StatusBadgeComponent,
  ],
  template: `
    <div class="page" *ngIf="inspection() as insp">
      <div class="page-header">
        <div>
          <a routerLink="/inspections" class="small back">&larr; Inspections</a>
          <h1>
            Inspection #{{ insp.id }}
            <span class="badge" [ngClass]="insp.inspection_type === 'pre_rental' ? 'badge-info' : 'badge-warn'">
              {{ insp.inspection_type === 'pre_rental' ? 'Pre-rental' : 'Post-rental' }}
            </span>
            <app-status-badge [status]="insp.status" />
          </h1>
          <p>
            <a [routerLink]="['/vehicles', insp.vehicle_id]">{{ insp.vehicle?.registration }}</a>
            · {{ insp.vehicle?.make }} {{ insp.vehicle?.model }}
            · {{ insp.inspector?.full_name }}
            · {{ insp.created_at | date: 'd MMM y, HH:mm' }}
          </p>
        </div>
        <div class="row">
          <a
            [routerLink]="['/comparison']"
            [queryParams]="{ vehicle_id: insp.vehicle_id, rental_ref: insp.rental_ref }"
            class="btn"
          >Compare pre / post</a>
          <button class="btn" (click)="downloadReport()" [disabled]="downloading()">
            <span class="spinner" *ngIf="downloading()"></span> Export PDF
          </button>
        </div>
      </div>

      <app-model-banner />

      <div class="summary card" *ngIf="insp.images.length">
        <div class="card-body">
          <div class="summary-grid">
            <div>
              <div class="label">Damage detected</div>
              <div class="chips" *ngIf="insp.damage_classes.length">
                <app-damage-chip
                  *ngFor="let c of insp.damage_classes"
                  [className]="c"
                  [severity]="severityFor(c)"
                />
              </div>
              <div class="clean" *ngIf="!insp.damage_classes.length">
                No damage above threshold in any photograph.
              </div>
            </div>
            <div class="metrics">
              <div>
                <div class="label">Photographs</div>
                <div class="metric">{{ insp.images.length }}</div>
              </div>
              <div>
                <div class="label">Mean latency</div>
                <div class="metric">{{ meanLatency() !== null ? (meanLatency()! | number: '1.0-0') + ' ms' : '—' }}</div>
              </div>
              <div>
                <div class="label">Model</div>
                <div class="metric small-metric">{{ insp.images[0].model_name || '—' }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Upload -->
      <div class="card upload-card" *ngIf="canEdit(insp)">
        <div class="card-header"><h2>Add photographs</h2></div>
        <div class="card-body">
          <div
            class="dropzone"
            [class.dragging]="dragging()"
            (dragover)="onDragOver($event)"
            (dragleave)="dragging.set(false)"
            (drop)="onDrop($event)"
          >
            <input
              #fileInput
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              hidden
              (change)="onFilesPicked($event)"
            />
            <div class="drop-inner">
              <div class="drop-icon" aria-hidden="true">⇪</div>
              <p><strong>Drop photographs here</strong> or
                <button type="button" class="linkish" (click)="fileInput.click()">browse</button>
              </p>
              <p class="small muted">JPEG, PNG or WebP · up to 15 MB each</p>
            </div>
          </div>

          <div class="upload-controls">
            <div class="field angle">
              <label for="angle">Capture angle</label>
              <select id="angle" [(ngModel)]="captureAngle">
                <option *ngFor="let a of angles" [value]="a.value">{{ a.label }}</option>
              </select>
            </div>
            <div class="staged" *ngIf="staged().length">
              <span class="badge badge-info">{{ staged().length }} file{{ staged().length === 1 ? '' : 's' }} ready</span>
              <span class="small muted truncate">{{ stagedNames() }}</span>
              <button class="btn btn-sm btn-ghost" (click)="staged.set([])">Clear</button>
            </div>
            <div class="spacer"></div>
            <button
              class="btn btn-primary"
              [disabled]="!staged().length || uploading()"
              (click)="upload()"
            >
              <span class="spinner" *ngIf="uploading()"></span>
              {{ uploading() ? 'Analysing…' : 'Upload and analyse' }}
            </button>
          </div>

          <div class="alert alert-danger" *ngIf="uploadError()">{{ uploadError() }}</div>
        </div>
      </div>

      <!-- Results -->
      <div class="empty card" *ngIf="!insp.images.length">
        <h3>No photographs yet</h3>
        <p class="small">Upload the walk-around images to run damage analysis.</p>
      </div>

      <div class="results" *ngIf="insp.images.length">
        <div class="card image-card" *ngFor="let image of insp.images">
          <div class="card-header">
            <h3>{{ angleLabel(image.capture_angle) }}</h3>
            <app-status-badge [status]="image.status" />
            <div class="spacer"></div>
            <span class="small muted">{{ image.inference_ms ? (image.inference_ms | number: '1.0-0') + ' ms' : '' }}</span>
            <button
              class="btn btn-sm btn-danger"
              *ngIf="canEdit(insp)"
              (click)="removeImage(image)"
              title="Delete this photograph"
            >Delete</button>
          </div>

          <app-annotated-image
            [path]="image.file_url"
            [detections]="image.detections"
            [alt]="'Inspection photograph, ' + angleLabel(image.capture_angle)"
          />

          <div class="card-body">
            <div class="alert alert-danger small" *ngIf="image.error_message">
              {{ image.error_message }}
            </div>

            <table class="scores">
              <tbody>
                <tr *ngFor="let d of sortedDetections(image)" [class.positive]="d.is_positive">
                  <td class="name">
                    <app-damage-chip
                      [className]="d.class_name"
                      [severity]="d.is_positive ? d.severity_hint : null"
                    />
                  </td>
                  <td>
                    <app-confidence-bar
                      [confidence]="d.confidence"
                      [threshold]="d.threshold"
                      [colour]="colourFor(d.class_name)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>

            <div class="file-meta small muted">
              <span class="truncate">{{ image.original_filename }}</span>
              <span>{{ image.width }}×{{ image.height }}</span>
              <span>{{ image.size_bytes / 1024 | number: '1.0-0' }} KB</span>
            </div>
            <div class="hash mono" [title]="'SHA-256 of the stored file: ' + image.sha256">
              sha256 {{ image.sha256.slice(0, 16) }}…
            </div>
          </div>
        </div>
      </div>

      <div class="notes card" *ngIf="insp.notes">
        <div class="card-header"><h2>Inspector notes</h2></div>
        <div class="card-body"><p class="small">{{ insp.notes }}</p></div>
      </div>
    </div>

    <div class="page" *ngIf="loading()">
      <div class="loading-row"><span class="spinner"></span> Loading inspection…</div>
    </div>
    <div class="page" *ngIf="error()">
      <div class="alert alert-danger">{{ error() }}</div>
    </div>
  `,
  styles: [
    `
      .back { display: inline-block; margin-bottom: 6px; }
      .page-header h1 { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }

      .summary { margin-bottom: 16px; }
      .summary-grid { display: flex; gap: 28px; justify-content: space-between; flex-wrap: wrap; }
      .label {
        font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--ink-500); font-weight: 650; margin-bottom: 6px;
      }
      .chips { display: flex; flex-wrap: wrap; gap: 5px; }
      .clean { font-size: 0.8125rem; color: var(--ok-600); font-weight: 550; }
      .metrics { display: flex; gap: 26px; }
      .metric { font-size: 1.25rem; font-weight: 700; color: var(--brand-900); font-variant-numeric: tabular-nums; }
      .small-metric { font-size: 0.875rem; font-weight: 600; }

      .upload-card { margin-bottom: 16px; }
      .dropzone {
        border: 1.5px dashed var(--border-strong);
        border-radius: var(--radius);
        background: var(--surface-alt);
        padding: 26px;
        text-align: center;
        transition: border-color 0.14s ease, background 0.14s ease;
      }
      .dropzone.dragging { border-color: var(--brand-500); background: var(--brand-050); }
      .drop-icon { font-size: 1.6rem; color: var(--brand-300); }
      .dropzone p { margin: 6px 0 0; font-size: 0.8125rem; }
      .linkish {
        background: none; border: none; padding: 0; font: inherit;
        color: var(--brand-500); text-decoration: underline; cursor: pointer;
      }
      .upload-controls { display: flex; align-items: flex-end; gap: 14px; margin-top: 14px; flex-wrap: wrap; }
      .angle { max-width: 190px; }
      .staged { display: flex; align-items: center; gap: 9px; min-width: 0; max-width: 340px; padding-bottom: 3px; }

      .results {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
        gap: 16px;
      }
      .image-card { overflow: hidden; }
      .image-card .card-header h3 { font-size: 0.875rem; }
      .image-card .card-body { padding: 12px 14px 14px; }

      table.scores { width: 100%; border-collapse: collapse; }
      table.scores td { padding: 3px 0; vertical-align: middle; }
      table.scores td.name { width: 132px; padding-right: 10px; }
      table.scores tr:not(.positive) { opacity: 0.55; }

      .file-meta { display: flex; gap: 10px; margin-top: 12px; padding-top: 9px; border-top: 1px solid var(--border); }
      .file-meta span:first-child { flex: 1; min-width: 0; }
      .hash { margin-top: 3px; color: var(--ink-400); }

      .notes { margin-top: 16px; }
      .loading-row { display: flex; align-items: center; gap: 9px; color: var(--ink-500); font-size: 0.8125rem; }
      .empty.card { padding: 40px; }
    `,
  ],
})
export class InspectionDetailComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly damageClasses = inject(DamageClassService);
  private readonly downloads = inject(DownloadService);
  private readonly router = inject(Router);

  @Input() id!: string;

  readonly angles = CAPTURE_ANGLES;

  readonly inspection = signal<Inspection | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly staged = signal<File[]>([]);
  readonly uploading = signal(false);
  readonly uploadError = signal<string | null>(null);
  readonly dragging = signal(false);
  readonly downloading = signal(false);

  captureAngle: CaptureAngle = 'front';

  readonly meanLatency = computed(() => {
    const timings = (this.inspection()?.images ?? [])
      .map((image) => image.inference_ms)
      .filter((ms): ms is number => ms !== null);
    if (!timings.length) return null;
    return timings.reduce((sum, ms) => sum + ms, 0) / timings.length;
  });

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.api.getInspection(Number(this.id)).subscribe({
      next: (inspection) => {
        this.inspection.set(inspection);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.error.set('Could not load this inspection.');
      },
    });
  }

  canEdit(inspection: Inspection): boolean {
    const user = this.auth.user();
    return !!user && (user.role === 'admin' || user.id === inspection.inspector_id);
  }

  angleLabel(angle: CaptureAngle): string {
    return CAPTURE_ANGLES.find((a) => a.value === angle)?.label ?? angle;
  }

  colourFor(className: string): string {
    return this.damageClasses.colour(className);
  }

  severityFor(className: string) {
    // Strongest supporting detection decides the severity shown for the class.
    const detections = (this.inspection()?.images ?? [])
      .flatMap((image) => image.detections)
      .filter((d) => d.class_name === className && d.is_positive)
      .sort((a, b) => b.confidence - a.confidence);
    return detections[0]?.severity_hint ?? null;
  }

  sortedDetections(image: InspectionImage) {
    return [...image.detections].sort((a, b) => {
      if (a.is_positive !== b.is_positive) return a.is_positive ? -1 : 1;
      return b.confidence - a.confidence;
    });
  }

  stagedNames(): string {
    return this.staged().map((file) => file.name).join(', ');
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    this.stage(Array.from(event.dataTransfer?.files ?? []));
  }

  onFilesPicked(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.stage(Array.from(input.files ?? []));
    // Reset so re-picking the same file still fires a change event.
    input.value = '';
  }

  private stage(files: File[]): void {
    const images = files.filter((file) => file.type.startsWith('image/'));
    if (images.length !== files.length) {
      this.uploadError.set('Some files were skipped: only images can be analysed.');
    }
    this.staged.set([...this.staged(), ...images]);
  }

  upload(): void {
    const inspection = this.inspection();
    if (!inspection || !this.staged().length) return;

    this.uploading.set(true);
    this.uploadError.set(null);

    this.api.uploadImages(inspection.id, this.staged(), this.captureAngle, true).subscribe({
      next: () => {
        this.staged.set([]);
        this.uploading.set(false);
        this.reload();
      },
      error: (err) => {
        this.uploading.set(false);
        this.uploadError.set(err?.error?.detail ?? 'Upload failed.');
      },
    });
  }

  removeImage(image: InspectionImage): void {
    const inspection = this.inspection();
    if (!inspection) return;
    if (!confirm(`Delete this photograph from inspection #${inspection.id}?`)) return;

    this.api.deleteImage(inspection.id, image.id).subscribe({
      next: () => this.reload(),
      error: () => this.uploadError.set('Could not delete the photograph.'),
    });
  }

  downloadReport(): void {
    const inspection = this.inspection();
    if (!inspection) return;

    this.downloading.set(true);
    this.api.inspectionReport(inspection.id).subscribe({
      next: (blob) => {
        this.downloads.save(
          blob,
          `inspection-${inspection.id}-${inspection.vehicle?.registration ?? 'vehicle'}.pdf`,
        );
        this.downloading.set(false);
      },
      error: () => {
        this.downloading.set(false);
        this.uploadError.set('Could not generate the report.');
      },
    });
  }
}
