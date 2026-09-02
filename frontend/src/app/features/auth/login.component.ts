import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';
import { DamageClassService } from '../../core/services/damage-class.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <div class="split">
      <section class="pitch">
        <div class="brand">
          <div class="mark">DT</div>
          <span>DriveTime</span>
        </div>
        <h1>Vehicle damage inspection</h1>
        <p>
          Deep-learning assisted pre- and post-rental condition assessment. Photograph the
          walk-around, get a classified, timestamped damage record, and settle disputes with
          an objective before-and-after comparison.
        </p>
        <ul>
          <li><span>1</span> Capture the walk-around at check-out and check-in</li>
          <li><span>2</span> The model classifies damage across six categories</li>
          <li><span>3</span> Export an evidentiary PDF for the rental file</li>
        </ul>
        <p class="fine">
          MSc dissertation prototype &mdash; Asia Pacific Institute of Information Technology.
        </p>
      </section>

      <section class="panel">
        <div class="card form-card">
          <div class="card-body">
            <h2>Sign in</h2>
            <p class="muted small">Use your DriveTime inspection account.</p>

            <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
              <div class="field">
                <label for="email">Email</label>
                <input id="email" type="email" formControlName="email" autocomplete="username" />
                <span class="error" *ngIf="showError('email')">Enter a valid email address.</span>
              </div>

              <div class="field">
                <label for="password">Password</label>
                <input
                  id="password"
                  type="password"
                  formControlName="password"
                  autocomplete="current-password"
                />
                <span class="error" *ngIf="showError('password')">Password is required.</span>
              </div>

              <div class="alert alert-danger" *ngIf="error()">{{ error() }}</div>

              <button class="btn btn-primary btn-block" type="submit" [disabled]="busy()">
                <span class="spinner" *ngIf="busy()"></span>
                {{ busy() ? 'Signing in…' : 'Sign in' }}
              </button>
            </form>

            <div class="demo">
              <div class="demo-title">Seeded accounts</div>
              <button type="button" class="demo-row" (click)="fill('admin@drivetime.lk', 'ChangeMe123!')">
                <strong>admin&#64;drivetime.lk</strong><span>Administrator</span>
              </button>
              <button
                type="button"
                class="demo-row"
                (click)="fill('inspector@drivetime.lk', 'Inspector123!')"
              >
                <strong>inspector&#64;drivetime.lk</strong><span>Inspector</span>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  `,
  styles: [
    `
      .split { display: grid; grid-template-columns: 1.1fr 1fr; min-height: 100vh; }

      .pitch {
        background: linear-gradient(160deg, var(--brand-900), var(--brand-700) 62%, #24507f);
        color: #dbe5f2;
        padding: 48px 52px;
        display: flex;
        flex-direction: column;
        justify-content: center;
      }
      .pitch h1 { color: #fff; font-size: 2rem; margin-bottom: 14px; max-width: 12ch; }
      .pitch p { max-width: 46ch; line-height: 1.6; color: #b9cade; }
      .brand { display: flex; align-items: center; gap: 11px; margin-bottom: 40px; }
      .brand span { color: #fff; font-weight: 650; letter-spacing: 0.01em; }
      .mark {
        width: 34px; height: 34px; border-radius: 9px;
        background: rgba(255, 255, 255, 0.16); color: #fff;
        display: grid; place-items: center; font-weight: 750; font-size: 0.8125rem;
      }
      .pitch ul { list-style: none; padding: 0; margin: 28px 0 0; display: grid; gap: 13px; }
      .pitch li {
        display: flex; align-items: center; gap: 12px;
        font-size: 0.875rem; color: #cddaea;
      }
      .pitch li span {
        width: 24px; height: 24px; flex: none; border-radius: 50%;
        background: rgba(255, 255, 255, 0.13); color: #fff;
        display: grid; place-items: center; font-size: 0.6875rem; font-weight: 700;
      }
      .fine { margin-top: 40px; font-size: 0.75rem; color: #8fa5c2; }

      .panel { display: grid; place-items: center; padding: 32px; background: var(--surface-alt); }
      .form-card { width: 100%; max-width: 388px; box-shadow: var(--shadow); }
      .form-card h2 { margin-bottom: 2px; }
      form { display: grid; gap: 14px; margin-top: 20px; }
      form .btn { margin-top: 4px; }

      .demo { margin-top: 22px; border-top: 1px solid var(--border); padding-top: 14px; }
      .demo-title {
        font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--ink-500); font-weight: 650; margin-bottom: 8px;
      }
      .demo-row {
        display: flex; justify-content: space-between; align-items: center; gap: 10px;
        width: 100%; padding: 7px 10px; margin-bottom: 5px;
        background: var(--surface-alt); border: 1px solid var(--border);
        border-radius: var(--radius-sm); cursor: pointer; font: inherit; text-align: left;
      }
      .demo-row:hover { background: var(--brand-050); border-color: var(--brand-300); }
      .demo-row strong { font-size: 0.75rem; font-weight: 600; }
      .demo-row span { font-size: 0.6875rem; color: var(--ink-500); }

      @media (max-width: 900px) {
        .split { grid-template-columns: 1fr; }
        .pitch { padding: 32px 24px; }
        .pitch ul, .fine { display: none; }
      }
    `,
  ],
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly damageClasses = inject(DamageClassService);

  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  showError(control: 'email' | 'password'): boolean {
    const field = this.form.controls[control];
    return field.invalid && field.touched;
  }

  fill(email: string, password: string): void {
    this.form.setValue({ email, password });
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.busy.set(true);
    this.error.set(null);

    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: () => {
        this.damageClasses.load();
        const redirect = this.route.snapshot.queryParamMap.get('redirect') ?? '/dashboard';
        void this.router.navigateByUrl(redirect);
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(
          err?.error?.detail ??
            'Could not sign in. Check the API is running on http://localhost:8000.',
        );
      },
    });
  }
}
