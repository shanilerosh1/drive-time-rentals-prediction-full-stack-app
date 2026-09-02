import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

/**
 * A score against its own decision threshold. The threshold marker matters:
 * each class has a different F1-optimised cut-off, so a bare percentage is
 * not interpretable on its own.
 */
@Component({
  selector: 'app-confidence-bar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="wrap" [title]="tooltip">
      <div class="track">
        <div class="fill" [style.width.%]="confidence * 100" [style.background]="colour"></div>
        <div class="threshold" [style.left.%]="threshold * 100"></div>
      </div>
      <span class="value" [class.dim]="!isPositive">{{ confidence * 100 | number: '1.0-1' }}%</span>
    </div>
  `,
  styles: [
    `
      .wrap { display: flex; align-items: center; gap: 8px; min-width: 128px; }
      .track {
        position: relative;
        flex: 1;
        height: 7px;
        background: var(--surface-sunken);
        border-radius: 4px;
        overflow: hidden;
      }
      .fill { height: 100%; border-radius: 4px; transition: width 0.3s ease; }
      .threshold {
        position: absolute;
        top: -2px;
        width: 2px;
        height: 11px;
        background: var(--ink-400);
        transform: translateX(-1px);
      }
      .value {
        font-variant-numeric: tabular-nums;
        font-size: 0.75rem;
        font-weight: 600;
        min-width: 40px;
        text-align: right;
      }
      .value.dim { color: var(--ink-400); font-weight: 500; }
    `,
  ],
})
export class ConfidenceBarComponent {
  @Input({ required: true }) confidence = 0;
  @Input({ required: true }) threshold = 0.5;
  @Input() colour = 'var(--brand-500)';

  get isPositive(): boolean {
    return this.confidence >= this.threshold;
  }

  get tooltip(): string {
    const verdict = this.isPositive ? 'above' : 'below';
    return (
      `Confidence ${(this.confidence * 100).toFixed(1)}% - ` +
      `${verdict} this class's threshold of ${(this.threshold * 100).toFixed(1)}%`
    );
  }
}
