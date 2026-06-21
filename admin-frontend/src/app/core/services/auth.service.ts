import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError } from 'rxjs';
import { LoginRequest, LoginResponse, PlatformUser } from '../models';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly API = `${environment.apiUrl}/auth`;
  private readonly TOKEN_KEY = 'platform_access_token';
  private readonly REFRESH_KEY = 'platform_refresh_token';
  private readonly USER_KEY = 'platform_user';

  currentUser = signal<PlatformUser | null>(this.loadStoredUser());
  isLoggedIn = computed(() => this.currentUser() !== null);

  constructor(private http: HttpClient, private router: Router) {}

  login(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.API}/login`, credentials).pipe(
      tap(response => {
        if (!response.user.is_platform_admin) {
          throw new Error('No tenés acceso a este panel. Esta cuenta no es de administrador de plataforma.');
        }
        localStorage.setItem(this.TOKEN_KEY, response.access_token);
        localStorage.setItem(this.REFRESH_KEY, response.refresh_token);
        localStorage.setItem(this.USER_KEY, JSON.stringify(response.user));
        this.currentUser.set(response.user);
      }),
      catchError(err => {
        const message = err.error?.error || err.message || 'Error al iniciar sesión';
        return throwError(() => new Error(message));
      })
    );
  }

  logout(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.REFRESH_KEY);
    localStorage.removeItem(this.USER_KEY);
    this.currentUser.set(null);
    this.router.navigate(['/login']);
  }

  getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  refreshToken(): Observable<{ access_token: string }> {
    const refreshToken = localStorage.getItem(this.REFRESH_KEY);
    return this.http.post<{ access_token: string }>(
      `${this.API}/refresh`,
      {},
      { headers: { Authorization: `Bearer ${refreshToken}` } }
    ).pipe(
      tap(response => localStorage.setItem(this.TOKEN_KEY, response.access_token))
    );
  }

  private loadStoredUser(): PlatformUser | null {
    try {
      const stored = localStorage.getItem(this.USER_KEY);
      const user = stored ? JSON.parse(stored) : null;
      return user?.is_platform_admin ? user : null;
    } catch {
      return null;
    }
  }
}
