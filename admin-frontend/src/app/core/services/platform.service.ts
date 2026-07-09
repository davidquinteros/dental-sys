import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Clinic, ClinicDetail, DashboardStats, PlatformUser,
  SubscriptionPayment, SubscriptionTier,
} from '../models';

@Injectable({ providedIn: 'root' })
export class PlatformService {
  private readonly API = `${environment.apiUrl}/platform`;

  constructor(private http: HttpClient) {}

  getDashboard(): Observable<DashboardStats> {
    return this.http.get<DashboardStats>(`${this.API}/dashboard`);
  }

  getClinics(status?: string): Observable<{ clinics: Clinic[]; total: number }> {
    const params = status ? { params: { status } } : {};
    return this.http.get<{ clinics: Clinic[]; total: number }>(`${this.API}/clinics`, params);
  }

  getClinic(id: number): Observable<ClinicDetail> {
    return this.http.get<ClinicDetail>(`${this.API}/clinics/${id}`);
  }

  createClinic(data: {
    name: string; admin_email: string; admin_password: string;
    admin_first_name?: string; admin_last_name?: string; subscription_tier_id?: number | null;
  }): Observable<{ clinic: Clinic; message: string }> {
    return this.http.post<{ clinic: Clinic; message: string }>(`${this.API}/clinics`, data);
  }

  updateClinic(id: number, data: Partial<{
    name: string; is_active: boolean; subscription_tier_id: number | null;
    subscription_status: string; notes: string;
    plan_started_at: string | null; plan_expires_at: string | null;
    address: string | null; phone: string | null; logo_url: string | null;
  }>): Observable<{ clinic: Clinic; message: string }> {
    return this.http.put<{ clinic: Clinic; message: string }>(`${this.API}/clinics/${id}`, data);
  }

  resetAdminPassword(clinicId: number, userId?: number): Observable<{
    user: PlatformUser; temporary_password: string; message: string;
  }> {
    return this.http.post<{ user: PlatformUser; temporary_password: string; message: string }>(
      `${this.API}/clinics/${clinicId}/reset-admin-password`, userId ? { user_id: userId } : {}
    );
  }

  getTiers(): Observable<{ tiers: SubscriptionTier[] }> {
    return this.http.get<{ tiers: SubscriptionTier[] }>(`${this.API}/subscription-tiers`);
  }

  createTier(data: {
    name: string; code: string; monthly_price: number; max_users?: number | null; description?: string;
  }): Observable<{ tier: SubscriptionTier; message: string }> {
    return this.http.post<{ tier: SubscriptionTier; message: string }>(`${this.API}/subscription-tiers`, data);
  }

  updateTier(id: number, data: Partial<{
    name: string; monthly_price: number; max_users: number | null; description: string; is_active: boolean;
  }>): Observable<{ tier: SubscriptionTier; message: string }> {
    return this.http.put<{ tier: SubscriptionTier; message: string }>(`${this.API}/subscription-tiers/${id}`, data);
  }

  getPayments(clinicId: number): Observable<{ payments: SubscriptionPayment[] }> {
    return this.http.get<{ payments: SubscriptionPayment[] }>(`${this.API}/clinics/${clinicId}/payments`);
  }

  recordPayment(clinicId: number, data: {
    amount: number; payment_date?: string; period_start?: string; period_end?: string; notes?: string;
  }): Observable<{ payment: SubscriptionPayment; clinic: Clinic; message: string }> {
    return this.http.post<{ payment: SubscriptionPayment; clinic: Clinic; message: string }>(
      `${this.API}/clinics/${clinicId}/payments`, data
    );
  }
}
