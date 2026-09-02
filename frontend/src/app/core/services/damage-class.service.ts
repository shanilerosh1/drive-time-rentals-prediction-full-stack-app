import { Injectable, signal } from '@angular/core';
import { shareReplay, tap } from 'rxjs';

import { ApiService } from './api.service';
import { DamageClass } from '../models/api.models';

/**
 * The damage taxonomy (labels, colours, thresholds, per-class test metrics) is
 * owned by the backend so the UI cannot drift from the model. Loaded once and
 * cached for the session.
 */
@Injectable({ providedIn: 'root' })
export class DamageClassService {
  private readonly _classes = signal<DamageClass[]>([]);
  readonly classes = this._classes.asReadonly();

  private request$ = this.api.damageClasses().pipe(
    tap(({ classes }) => this._classes.set(classes)),
    shareReplay({ bufferSize: 1, refCount: false }),
  );

  constructor(private readonly api: ApiService) {}

  load(): void {
    this.request$.subscribe({ error: () => this._classes.set([]) });
  }

  label(name: string): string {
    return this._classes().find((c) => c.name === name)?.label ?? this.titleCase(name);
  }

  colour(name: string): string {
    return this._classes().find((c) => c.name === name)?.colour ?? '#6B7280';
  }

  f1(name: string): number | null {
    return this._classes().find((c) => c.name === name)?.test_metrics?.f1 ?? null;
  }

  private titleCase(name: string): string {
    return name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
}
