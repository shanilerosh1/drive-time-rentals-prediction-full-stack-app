import { TestBed } from '@angular/core/testing';
import { Router, UrlTree } from '@angular/router';

import { adminGuard, authGuard } from './auth.guard';
import { AuthService } from '../services/auth.service';

function run(guard: typeof authGuard, opts: { authed: boolean; admin?: boolean; url?: string }) {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      {
        provide: AuthService,
        useValue: {
          isAuthenticated: () => opts.authed,
          isAdmin: () => opts.admin ?? false,
        },
      },
    ],
  });
  const router = TestBed.inject(Router);
  return TestBed.runInInjectionContext(() =>
    guard({} as never, { url: opts.url ?? '/dashboard' } as never),
  );
}

describe('authGuard', () => {
  it('lets a signed-in user through', () => {
    expect(run(authGuard, { authed: true })).toBeTrue();
  });

  it('redirects a signed-out user to the login page', () => {
    const result = run(authGuard, { authed: false });
    expect(result instanceof UrlTree).toBeTrue();
    expect((result as UrlTree).toString()).toContain('/login');
  });

  it('remembers where the user was heading', () => {
    const result = run(authGuard, { authed: false, url: '/inspections/42' });
    // So that signing in returns them there rather than to the dashboard.
    expect((result as UrlTree).toString()).toContain('redirect');
    expect(decodeURIComponent((result as UrlTree).toString())).toContain('/inspections/42');
  });
});

describe('adminGuard', () => {
  it('lets an administrator through', () => {
    expect(run(adminGuard, { authed: true, admin: true })).toBeTrue();
  });

  it('sends a non-admin back to the dashboard rather than the login page', () => {
    const result = run(adminGuard, { authed: true, admin: false });
    expect((result as UrlTree).toString()).toContain('/dashboard');
  });
});
