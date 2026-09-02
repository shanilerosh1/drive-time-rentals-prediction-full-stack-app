import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';

/**
 * Attaches the bearer token to our own API calls and signs the user out on a
 * 401, which is how an expired token surfaces.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.token;

  const isApiCall = req.url.startsWith(environment.apiBase) || req.url.startsWith('/api/');
  const request =
    token && isApiCall
      ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : req;

  return next(request).pipe(
    catchError((error: HttpErrorResponse) => {
      const isLoginAttempt = req.url.includes('/auth/login');
      if (error.status === 401 && !isLoginAttempt) {
        auth.logout();
      }
      return throwError(() => error);
    }),
  );
};
