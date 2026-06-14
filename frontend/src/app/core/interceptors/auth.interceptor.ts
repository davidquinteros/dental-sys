import { HttpInterceptorFn, HttpRequest, HttpHandlerFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';
import { catchError, switchMap, throwError } from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
) => {
  const authService = inject(AuthService);
  const token = authService.getToken();

  // Don't intercept auth endpoints (except /me and /change-password)
  const isAuthEndpoint = req.url.includes('/api/auth/login') ||
    req.url.includes('/api/auth/refresh');

  if (isAuthEndpoint) {
    return next(req);
  }

  const authReq = token
    ? req.clone({ headers: req.headers.set('Authorization', `Bearer ${token}`) })
    : req;

  return next(authReq).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !req.url.includes('/api/auth/refresh')) {
        // Try to refresh token
        return authService.refreshToken().pipe(
          switchMap(response => {
            const retryReq = req.clone({
              headers: req.headers.set('Authorization', `Bearer ${response.access_token}`),
            });
            return next(retryReq);
          }),
          catchError(() => {
            authService.logout();
            return throwError(() => error);
          })
        );
      }
      return throwError(() => error);
    })
  );
};
