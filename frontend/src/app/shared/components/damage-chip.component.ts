import { CommonModule } from '@angular/common';
import { Component, Input, inject } from '@angular/core';

import { DamageClassService } from '../../core/services/damage-class.service';
import { SeverityHint } from '../../core/models/api.models';

@Component({
  selector: 'app-damage-chip',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span class="chip" [style.--chip]="colour" [title]="tooltip">
      <span class="dot"></span>
      {{ label }}
      <span class="sev" *ngIf="severity && severity !== 'none'">{{ severity }}</span>
    </span>
  `,
  styles: [
    `
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 2px 9px 2px 7px;
        border-radius: 999px;
        font-size: 0.6875rem;
        font-weight: 600;
        background: color-mix(in srgb, var(--chip) 12%, white);
        color: color-mix(in srgb, var(--chip) 78%, black);
        border: 1px solid color-mix(in srgb, var(--chip) 32%, white);
        white-space: nowrap;
      }
      .dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--chip);
        flex: none;
      }
      .sev {
        font-size: 0.625rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        opacity: 0.72;
        font-weight: 700;
      }
    `,
  ],
})
export class DamageChipComponent {
  private readonly classes = inject(DamageClassService);

  @Input({ required: true }) className = '';
  @Input() severity: SeverityHint | null = null;

  get label(): string {
    return this.classes.label(this.className);
  }

  get colour(): string {
    return this.classes.colour(this.className);
  }

  get tooltip(): string {
    const f1 = this.classes.f1(this.className);
    const base = this.label;
    const sev = this.severity && this.severity !== 'none' ? ` - severity hint: ${this.severity}` : '';
    return f1 !== null ? `${base}${sev} (test-set F1 ${f1.toFixed(2)})` : `${base}${sev}`;
  }
}
