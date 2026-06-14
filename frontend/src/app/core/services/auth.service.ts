import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError } from 'rxjs';
import { LoginRequest, LoginResponse, User, UserRole } from '../models';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly API = `${environment.apiUrl}/auth`;
  private readonly TOKEN_KEY = 'dental_access_token';
  private readonly REFRESH_KEY = 'dental_refresh_token';
  private readonly USER_KEY = 'dental_user';

  // Reactive user state using Angular signals
  currentUser = signal<User | null>(this.loadStoredUser());
  isLoggedIn = computed(() => this.currentUser() !== null);

  constructor(private http: HttpClient, private router: Router) {}

  login(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.API}/login`, credentials).pipe(
      tap(response => {
        localStorage.setItem(this.TOKEN_KEY, response.access_token);
        localStorage.setItem(this.REFRESH_KEY, response.refresh_token);
        localStorage.setItem(this.USER_KEY, JSON.stringify(response.user));
        this.currentUser.set(response.user);
      }),
      catchError(err => {
        const message = err.error?.error || 'Error al iniciar sesión';
        return throwError(() => new Error(message));
      })
    );
  }

  logout(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.REFRESH_KEY);
    localStorage.removeItem(this.USER_KEY);
    this.currentUser.set(null);
    this.router.navigate(['/auth/login']);
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
      tap(response => {
        localStorage.setItem(this.TOKEN_KEY, response.access_token);
      })
    );
  }

  hasRole(...roles: UserRole[]): boolean {
    const user = this.currentUser();
    if (!user) return false;
    return roles.includes(user.role);
  }

  isAdmin = computed(() => this.currentUser()?.role === 'admin');
  isDoctor = computed(() => this.currentUser()?.role === 'doctor');
  isReceptionist = computed(() => this.currentUser()?.role === 'receptionist');
  isAssistant = computed(() => this.currentUser()?.role === 'assistant');
  canManageBilling = computed(() =>
    this.hasRole('admin', 'receptionist')
  );
  canManageTreatments = computed(() =>
    this.hasRole('admin', 'doctor', 'assistant')
  );
  canManageUsers = computed(() => this.isAdmin());
  canViewAll = computed(() => this.hasRole('admin', 'receptionist'));

  private loadStoredUser(): User | null {
    try {
      const stored = localStorage.getItem(this.USER_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  }

  changePassword(currentPassword: string, newPassword: string): Observable<any> {
    return this.http.put(`${this.API}/change-password`, {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }
}
