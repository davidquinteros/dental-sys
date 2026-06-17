import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AppPage, PermissionMatrixResponse, MyPermissionsResponse, PermissionMatrix,
} from '../models';

const API = `${environment.apiUrl}/permissions`;
const STORAGE_KEY = 'dental_permissions';

@Injectable({ providedIn: 'root' })
export class PermissionService {
  private viewableKeys = signal<string[]>(this.loadStored());
  private pagesCache = signal<AppPage[]>([]);

  /** Page keys the current user can view */
  viewable = computed(() => this.viewableKeys());

  constructor(private http: HttpClient) {}

  /** Call this right after login / on app init to populate permission cache. */
  load(): Observable<MyPermissionsResponse> {
    return this.http.get<MyPermissionsResponse>(`${API}/me`).pipe(
      tap(res => {
        this.viewableKeys.set(res.viewable_pages);
        this.pagesCache.set(res.pages);
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(res.viewable_pages));
      }),
    );
  }

  /** Returns the list of accessible AppPage objects (for sidebar nav). */
  accessiblePages(): AppPage[] {
    return this.pagesCache();
  }

  /** True if the current user's role can view the given page key. */
  canView(pageKey: string): boolean {
    return this.viewableKeys().includes(pageKey);
  }

  /** Clear cached permissions on logout. */
  clear(): void {
    this.viewableKeys.set([]);
    this.pagesCache.set([]);
    sessionStorage.removeItem(STORAGE_KEY);
  }

  // ── Admin API ──────────────────────────────────────────────────────────────

  getMatrix(): Observable<PermissionMatrixResponse> {
    return this.http.get<PermissionMatrixResponse>(`${API}/matrix`);
  }

  saveMatrix(matrix: PermissionMatrix): Observable<any> {
    return this.http.put(`${API}/matrix`, matrix);
  }

  getPages(): Observable<{ pages: AppPage[] }> {
    return this.http.get<{ pages: AppPage[] }>(`${API}/pages`);
  }

  createPage(data: Partial<AppPage>): Observable<{ page: AppPage }> {
    return this.http.post<{ page: AppPage }>(`${API}/pages`, data);
  }

  updatePage(id: number, data: Partial<AppPage>): Observable<{ page: AppPage }> {
    return this.http.put<{ page: AppPage }>(`${API}/pages/${id}`, data);
  }

  deletePage(id: number): Observable<any> {
    return this.http.delete(`${API}/pages/${id}`);
  }

  private loadStored(): string[] {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }
}
