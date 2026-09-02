import { HttpClient } from '@angular/common/http';
import { Injectable, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Token, User } from '../models/api.models';

const TOKEN_KEY = 'dt_access_token';
const USER_KEY = 'dt_user';

@Injectable({ providedIn: 'root' })
export class AuthService {
  /** Restored synchronously at construction so guards can decide on first navigation. */
  private readonly _user = signal<User | null>(this.restoreUser());
  private readonly _token = signal<string | null>(localStorage.getItem(TOKEN_KEY));

  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => this._token() !== null);
  readonly isAdmin = computed(() => this._user()?.role === 'admin');

  constructor(private readonly http: HttpClient, private readonly router: Router) {}

  get token(): string | null {
    return this._token();
  }

  login(email: string, password: string): Observable<Token> {
    return this.http
      .post<Token>(`${environment.apiBase}/auth/login`, { email, password })
      .pipe(tap((token) => this.persist(token)));
  }

  /** Confirms a restored token is still valid; used on app bootstrap. */
  refreshProfile(): Observable<User> {
    return this.http
      .get<User>(`${environment.apiBase}/auth/me`)
      .pipe(tap((user) => {
        this._user.set(user);
        localStorage.setItem(USER_KEY, JSON.stringify(user));
      }));
  }

  logout(redirect = true): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    this._token.set(null);
    this._user.set(null);
    if (redirect) {
      void this.router.navigate(['/login']);
    }
  }

  private persist(token: Token): void {
    localStorage.setItem(TOKEN_KEY, token.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(token.user));
    this._token.set(token.access_token);
    this._user.set(token.user);
  }

  private restoreUser(): User | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as User;
    } catch {
      // Corrupt entry from an older schema: drop it rather than crash boot.
      localStorage.removeItem(USER_KEY);
      return null;
    }
  }
}
