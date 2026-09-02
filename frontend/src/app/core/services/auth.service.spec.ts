import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';

import { environment } from '../../../environments/environment';
import { authInterceptor } from '../interceptors/auth.interceptor';
import { AuthService } from './auth.service';
import { Token, User } from '../models/api.models';

const USER: User = {
  id: 1,
  email: 'admin@drivetime.lk',
  full_name: 'System Administrator',
  role: 'admin',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
};

const TOKEN: Token = {
  access_token: 'header.payload.signature',
  token_type: 'bearer',
  expires_in: 28800,
  user: USER,
};

/** Build a fresh injector, so the service re-reads localStorage as it does on boot. */
function makeService(): { auth: AuthService; http: HttpTestingController; router: jasmine.SpyObj<Router> } {
  TestBed.resetTestingModule();
  const router = jasmine.createSpyObj<Router>('Router', ['navigate']);
  TestBed.configureTestingModule({
    providers: [
      AuthService,
      { provide: Router, useValue: router },
      provideHttpClient(withInterceptors([authInterceptor])),
      provideHttpClientTesting(),
    ],
  });
  return {
    auth: TestBed.inject(AuthService),
    http: TestBed.inject(HttpTestingController),
    router,
  };
}

describe('AuthService', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('starts signed out', () => {
    const { auth, http } = makeService();
    expect(auth.isAuthenticated()).toBeFalse();
    expect(auth.user()).toBeNull();
    http.verify();
  });

  it('stores the token and user after a successful login', () => {
    const { auth, http } = makeService();
    auth.login('admin@drivetime.lk', 'ChangeMe123!').subscribe();
    http.expectOne(`${environment.apiBase}/auth/login`).flush(TOKEN);

    expect(auth.isAuthenticated()).toBeTrue();
    expect(auth.isAdmin()).toBeTrue();
    expect(auth.token).toBe(TOKEN.access_token);
    http.verify();
  });

  it('restores the session on reload', () => {
    const first = makeService();
    first.auth.login('admin@drivetime.lk', 'ChangeMe123!').subscribe();
    first.http.expectOne(`${environment.apiBase}/auth/login`).flush(TOKEN);
    first.http.verify();

    // A new injector stands in for a reloaded browser tab.
    const { auth, http } = makeService();
    expect(auth.isAuthenticated()).toBeTrue();
    expect(auth.user()?.email).toBe(USER.email);
    http.verify();
  });

  it('clears everything on logout', () => {
    const { auth, http, router } = makeService();
    auth.login('a@example.com', 'x').subscribe();
    http.expectOne(`${environment.apiBase}/auth/login`).flush(TOKEN);

    auth.logout();
    expect(auth.isAuthenticated()).toBeFalse();
    expect(auth.user()).toBeNull();
    expect(localStorage.getItem('dt_access_token')).toBeNull();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
    http.verify();
  });

  it('discards a corrupt stored user rather than crashing on boot', () => {
    // An older release could have written a different shape here.
    localStorage.setItem('dt_user', '{not valid json');
    const { auth, http } = makeService();
    expect(auth.user()).toBeNull();
    expect(localStorage.getItem('dt_user')).toBeNull();
    http.verify();
  });

  it('reports a non-admin correctly', () => {
    const { auth, http } = makeService();
    auth.login('inspector@drivetime.lk', 'x').subscribe();
    http.expectOne(`${environment.apiBase}/auth/login`).flush({
      ...TOKEN,
      user: { ...USER, id: 2, role: 'inspector' as const },
    });
    expect(auth.isAuthenticated()).toBeTrue();
    expect(auth.isAdmin()).toBeFalse();
    http.verify();
  });
});
