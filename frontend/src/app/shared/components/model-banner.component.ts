import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';

import { ApiService } from '../../core/services/api.service';
import { ModelInfo } from '../../core/models/api.models';

/**
 * Standing notice about which model is answering. When no trained weights are
 * loaded, every finding in the app is a placeholder, and the user needs to
 * know that before they act on a report.
 */
@Component({
  selector: 'app-model-banner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="alert alert-warn" *ngIf="info() && !info()!.is_real">
      <span aria-hidden="true">⚠</span>
      <div>
        <strong>Placeholder predictions.</strong>
        No trained model weights are loaded, so damage findings are generated from a
        deterministic stub and carry no visual meaning. The workflow, reports and
        comparison logic are fully functional &mdash; drop
        <code class="mono">car_damage_classifier.pth</code> into
        <code class="mono">backend/models/</code> and restart to get real inference.
      </div>
    </div>
  `,
})
export class ModelBannerComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly info = signal<ModelInfo | null>(null);

  ngOnInit(): void {
    this.api.modelInfo().subscribe({
      next: (info) => this.info.set(info),
      // A failed probe should not block the page it sits on.
      error: () => this.info.set(null),
    });
  }
}
