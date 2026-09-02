import { CommonModule } from '@angular/common';
import { Component, Input, OnDestroy, OnInit, inject, signal } from '@angular/core';

import { ApiService } from '../../core/services/api.service';
import { DamageClassService } from '../../core/services/damage-class.service';
import { Detection } from '../../core/models/api.models';

/**
 * A photograph with its findings drawn over it.
 *
 * Boxes are positioned in percentages over the image, so they scale with the
 * container and need no canvas or resize handling. The classifier produces no
 * boxes, in which case this degrades to a labelled overlay in the corner -
 * when the YOLOv8 backend lands and `bbox` is populated, the same component
 * starts drawing localised damage with no change here.
 */
@Component({
  selector: 'app-annotated-image',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="stage">
      <div class="skeleton ph" *ngIf="loading()"></div>
      <img *ngIf="url()" [src]="url()" [alt]="alt" (load)="loading.set(false)" />

      <!-- Localised findings (detector backend) -->
      <div
        class="box"
        *ngFor="let d of boxed()"
        [style.left.%]="d.bbox!.x * 100"
        [style.top.%]="d.bbox!.y * 100"
        [style.width.%]="d.bbox!.w * 100"
        [style.height.%]="d.bbox!.h * 100"
        [style.--box]="colour(d.class_name)"
      >
        <span class="tag">{{ label(d.class_name) }} {{ d.confidence * 100 | number: '1.0-0' }}%</span>
      </div>

      <!-- Image-level findings (classifier backend) -->
      <div class="overlay" *ngIf="unboxed().length && showLabels">
        <span class="tag stacked" *ngFor="let d of unboxed()" [style.--box]="colour(d.class_name)">
          {{ label(d.class_name) }} {{ d.confidence * 100 | number: '1.0-0' }}%
        </span>
      </div>

      <div class="clean" *ngIf="!positives().length && !loading()">No damage above threshold</div>
    </div>
  `,
  styles: [
    `
      .stage {
        position: relative;
        width: 100%;
        background: #0f1420;
        border-radius: var(--radius-sm);
        overflow: hidden;
        line-height: 0;
      }
      .ph { position: absolute; inset: 0; }
      img { display: block; width: 100%; height: auto; }
      .box {
        position: absolute;
        border: 2px solid var(--box);
        border-radius: 3px;
        box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.35);
        pointer-events: none;
      }
      .box .tag { position: absolute; top: -19px; left: -2px; }
      .tag {
        display: inline-block;
        background: var(--box);
        color: #fff;
        font-size: 0.625rem;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 3px;
        line-height: 1.5;
        white-space: nowrap;
        text-shadow: 0 1px 1px rgba(0, 0, 0, 0.3);
      }
      .overlay {
        position: absolute;
        top: 8px;
        left: 8px;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 4px;
      }
      .clean {
        position: absolute;
        bottom: 8px;
        left: 8px;
        background: rgba(15, 20, 32, 0.78);
        color: #cfd8e6;
        font-size: 0.6875rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 3px;
        line-height: 1.6;
      }
    `,
  ],
})
export class AnnotatedImageComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly classes = inject(DamageClassService);

  @Input({ required: true }) path = '';
  @Input() detections: Detection[] = [];
  @Input() alt = '';
  @Input() showLabels = true;

  readonly url = signal<string | null>(null);
  readonly loading = signal(true);

  // Plain getters, not computed(): `detections` is a classic @Input, so a
  // computed() would cache its first value and never see a reassignment.
  positives(): Detection[] {
    return this.detections.filter((d) => d.is_positive);
  }

  boxed(): Detection[] {
    return this.positives().filter((d) => d.bbox !== null);
  }

  unboxed(): Detection[] {
    return this.positives().filter((d) => d.bbox === null);
  }

  ngOnInit(): void {
    this.api.fetchImageBlob(this.path).subscribe({
      next: (blob) => this.url.set(URL.createObjectURL(blob)),
      error: () => this.loading.set(false),
    });
  }

  ngOnDestroy(): void {
    const current = this.url();
    if (current) URL.revokeObjectURL(current);
  }

  label(name: string): string {
    return this.classes.label(name);
  }

  colour(name: string): string {
    return this.classes.colour(name);
  }
}
