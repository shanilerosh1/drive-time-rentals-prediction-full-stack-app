import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';

import { environment } from '../../../environments/environment';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from '../services/auth.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let auth: jasmine.SpyObj<AuthService>;

  function configure(token: string | null) {
    TestBed.resetTestingModule();
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['logout'], { token });
    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: jasmine.createSpyObj('Router', ['navigate']) },
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
  }

  it('attaches the bearer token to API calls', () => {
    configure('abc123');
    http.get(`${environment.apiBase}/vehicles`).subscribe();
    const req = backend.expectOne(`${environment.apiBase}/vehicles`);
    expect(req.request.headers.get('Authorization')).toBe('Bearer abc123');
    req.flush({});
    backend.verify();
  });

  it('sends no Authorization header when signed out', () => {
    configure(null);
    http.get(`${environment.apiBase}/health`).subscribe();
    const req = backend.expectOne(`${environment.apiBase}/health`);
    expect(req.request.headers.has('Authorization')).toBeFalse();
    req.flush({});
    backend.verify();
  });

  it('does not attach the token to third-party URLs', () => {
    configure('abc123');
    http.get('https://example.com/thing').subscribe();
    const req = backend.expectOne('https://example.com/thing');
    expect(req.request.headers.has('Authorization')).toBeFalse();
    req.flush({});
    backend.verify();
  });

  it('signs the user out when the API returns 401', () => {
    configure('expired');
    http.get(`${environment.apiBase}/vehicles`).subscribe({ error: () => undefined });
    backend.expectOne(`${environment.apiBase}/vehicles`)
      .flush({ detail: 'nope' }, { status: 401, statusText: 'Unauthorized' });
    expect(auth.logout).toHaveBeenCalled();
    backend.verify();
  });

  it('does NOT sign the user out when a login attempt is rejected', () => {
    // Otherwise a mistyped password would look like an expired session.
    configure(null);
    http.post(`${environment.apiBase}/auth/login`, {}).subscribe({ error: () => undefined });
    backend.expectOne(`${environment.apiBase}/auth/login`)
      .flush({ detail: 'Incorrect email or password.' },
             { status: 401, statusText: 'Unauthorized' });
    expect(auth.logout).not.toHaveBeenCalled();
    backend.verify();
  });

  it('leaves other error statuses alone', () => {
    configure('abc123');
    http.get(`${environment.apiBase}/vehicles`).subscribe({ error: () => undefined });
    backend.expectOne(`${environment.apiBase}/vehicles`)
      .flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    expect(auth.logout).not.toHaveBeenCalled();
    backend.verify();
  });
});
