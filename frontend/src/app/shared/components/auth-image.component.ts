import { CommonModule } from '@angular/common';
import { Component, Input, OnDestroy, OnInit, inject, signal } from '@angular/core';

import { ApiService } from '../../core/services/api.service';

/**
 * Inspection photographs sit behind bearer auth, so a plain <img src> cannot
 * load them. This fetches the bytes through HttpClient (picking up the auth
 * interceptor) and binds an object URL, revoking it on destroy.
 */
@Component({
  selector: 'app-auth-image',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="frame" [class.contain]="contain">
      <div class="skeleton ph" *ngIf="loading()"></div>
      <img *ngIf="url()" [src]="url()" [alt]="alt" (load)="loading.set(false)" />
      <div class="failed" *ngIf="failed()">Image unavailable</div>
    </div>
  `,
  styles: [
    `
      .frame {
        position: relative;
        width: 100%;
        height: 100%;
        background: var(--surface-sunken);
        overflow: hidden;
        border-radius: inherit;
      }
      .ph { position: absolute; inset: 0; }
      img { display: block; width: 100%; height: 100%; object-fit: cover; }
      .contain img { object-fit: contain; }
      .failed {
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        font-size: 0.75rem;
        color: var(--ink-500);
      }
    `,
  ],
})
export class AuthImageComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);

  @Input({ required: true }) path = '';
  @Input() alt = '';
  @Input() contain = false;

  readonly url = signal<string | null>(null);
  readonly loading = signal(true);
  readonly failed = signal(false);

  ngOnInit(): void {
    this.api.fetchImageBlob(this.path).subscribe({
      next: (blob) => this.url.set(URL.createObjectURL(blob)),
      error: () => {
        this.loading.set(false);
        this.failed.set(true);
      },
    });
  }

  ngOnDestroy(): void {
    const current = this.url();
    if (current) URL.revokeObjectURL(current);
  }
}
