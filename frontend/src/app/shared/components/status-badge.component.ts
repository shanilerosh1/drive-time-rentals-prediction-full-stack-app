import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { ImageStatus, InspectionStatus } from '../../core/models/api.models';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [CommonModule],
  template: `<span class="badge" [ngClass]="cssClass">{{ text }}</span>`,
})
export class StatusBadgeComponent {
  @Input({ required: true }) status!: InspectionStatus | ImageStatus;

  private static readonly MAP: Record<string, { text: string; css: string }> = {
    draft: { text: 'Draft', css: 'badge-neutral' },
    analysing: { text: 'Analysing', css: 'badge-info' },
    completed: { text: 'Completed', css: 'badge-ok' },
    failed: { text: 'Failed', css: 'badge-danger' },
    cancelled: { text: 'Cancelled', css: 'badge-neutral' },
    pending: { text: 'Pending', css: 'badge-warn' },
    analysed: { text: 'Analysed', css: 'badge-ok' },
  };

  get text(): string {
    return StatusBadgeComponent.MAP[this.status]?.text ?? this.status;
  }

  get cssClass(): string {
    return StatusBadgeComponent.MAP[this.status]?.css ?? 'badge-neutral';
  }
}
