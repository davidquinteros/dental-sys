import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Patient, Appointment, Treatment, TreatmentPlan,
  Invoice, Payment, PaymentPlan, DashboardData, User, Consultorio, AppointmentTypeItem
} from '../models';

const API = environment.apiUrl;

// ─── Patients ──────────────────────────────────────────────────────────────────
@Injectable({ providedIn: 'root' })
export class PatientService {
  constructor(private http: HttpClient) {}

  getAll(params: { page?: number; search?: string; per_page?: number } = {}): Observable<any> {
    let httpParams = new HttpParams();
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.search) httpParams = httpParams.set('search', params.search);
    if (params.per_page) httpParams = httpParams.set('per_page', params.per_page);
    return this.http.get(`${API}/patients/`, { params: httpParams });
  }

  getById(id: number, includeHistory = false): Observable<{ patient: Patient }> {
    return this.http.get<{ patient: Patient }>(
      `${API}/patients/${id}`,
      { params: new HttpParams().set('include_history', includeHistory) }
    );
  }

  getHistory(id: number): Observable<any> {
    return this.http.get(`${API}/patients/${id}/history`);
  }

  create(data: Partial<Patient>): Observable<{ patient: Patient }> {
    return this.http.post<{ patient: Patient }>(`${API}/patients/`, data);
  }

  update(id: number, data: Partial<Patient>): Observable<{ patient: Patient }> {
    return this.http.put<{ patient: Patient }>(`${API}/patients/${id}`, data);
  }

  delete(id: number): Observable<any> {
    return this.http.delete(`${API}/patients/${id}`);
  }

  getOdontogram(id: number): Observable<Record<string, any>> {
    return this.http.get<Record<string, any>>(`${API}/patients/${id}/odontogram`);
  }

  saveOdontogram(id: number, data: Record<string, any>): Observable<Record<string, any>> {
    return this.http.put<Record<string, any>>(`${API}/patients/${id}/odontogram`, data);
  }
}

// ─── Appointments ──────────────────────────────────────────────────────────────
@Injectable({ providedIn: 'root' })
export class AppointmentService {
  constructor(private http: HttpClient) {}

  getAll(params: Record<string, any> = {}): Observable<any> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        httpParams = httpParams.set(k, v);
      }
    });
    return this.http.get(`${API}/appointments/`, { params: httpParams });
  }

  getById(id: number): Observable<{ appointment: Appointment }> {
    return this.http.get<{ appointment: Appointment }>(`${API}/appointments/${id}`);
  }

  getToday(): Observable<{ appointments: Appointment[]; total: number }> {
    return this.http.get<{ appointments: Appointment[]; total: number }>(`${API}/appointments/today`);
  }

  checkAvailability(doctorId: number, date: string): Observable<any> {
    return this.http.get(`${API}/appointments/availability`, {
      params: new HttpParams().set('doctor_id', doctorId).set('date', date)
    });
  }

  create(data: Partial<Appointment>): Observable<{ appointment: Appointment }> {
    return this.http.post<{ appointment: Appointment }>(`${API}/appointments/`, data);
  }

  update(id: number, data: Partial<Appointment>): Observable<{ appointment: Appointment }> {
    return this.http.put<{ appointment: Appointment }>(`${API}/appointments/${id}`, data);
  }

  cancel(id: number, reason: string): Observable<any> {
    return this.http.post(`${API}/appointments/${id}/cancel`, { reason });
  }
}

// ─── Treatments ─────────────────────────────────────────────────────────────────
@Injectable({ providedIn: 'root' })
export class TreatmentService {
  constructor(private http: HttpClient) {}

  getAll(params: Record<string, any> = {}): Observable<any> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) httpParams = httpParams.set(k, v);
    });
    return this.http.get(`${API}/treatments/`, { params: httpParams });
  }

  create(data: Partial<Treatment>): Observable<{ treatment: Treatment }> {
    return this.http.post<{ treatment: Treatment }>(`${API}/treatments/`, data);
  }

  update(id: number, data: Partial<Treatment>): Observable<{ treatment: Treatment }> {
    return this.http.put<{ treatment: Treatment }>(`${API}/treatments/${id}`, data);
  }

  // Plans
  getPlans(params: Record<string, any> = {}): Observable<any> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) httpParams = httpParams.set(k, v);
    });
    return this.http.get(`${API}/treatments/plans`, { params: httpParams });
  }

  getPlan(id: number, includeSessions = false): Observable<{ treatment_plan: TreatmentPlan }> {
    return this.http.get<{ treatment_plan: TreatmentPlan }>(
      `${API}/treatments/plans/${id}`,
      { params: new HttpParams().set('include_sessions', includeSessions) }
    );
  }

  createPlan(data: Partial<TreatmentPlan>): Observable<{ treatment_plan: TreatmentPlan }> {
    return this.http.post<{ treatment_plan: TreatmentPlan }>(`${API}/treatments/plans`, data);
  }

  updatePlan(id: number, data: Partial<TreatmentPlan>): Observable<{ treatment_plan: TreatmentPlan }> {
    return this.http.put<{ treatment_plan: TreatmentPlan }>(`${API}/treatments/plans/${id}`, data);
  }
}

// ─── Billing ────────────────────────────────────────────────────────────────────
@Injectable({ providedIn: 'root' })
export class BillingService {
  constructor(private http: HttpClient) {}

  getInvoices(params: Record<string, any> = {}): Observable<any> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) httpParams = httpParams.set(k, v);
    });
    return this.http.get(`${API}/billing/invoices`, { params: httpParams });
  }

  getInvoice(id: number): Observable<{ invoice: Invoice }> {
    return this.http.get<{ invoice: Invoice }>(`${API}/billing/invoices/${id}`);
  }

  createInvoice(data: any): Observable<{ invoice: Invoice }> {
    return this.http.post<{ invoice: Invoice }>(`${API}/billing/invoices`, data);
  }

  addPayment(invoiceId: number, data: {
    amount: number; method: string; reference?: string; notes?: string
  }): Observable<any> {
    return this.http.post(`${API}/billing/invoices/${invoiceId}/payments`, data);
  }

  getPaymentPlans(params: Record<string, any> = {}): Observable<any> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) httpParams = httpParams.set(k, v);
    });
    return this.http.get(`${API}/billing/payment-plans`, { params: httpParams });
  }

  createPaymentPlan(data: any): Observable<{ payment_plan: PaymentPlan }> {
    return this.http.post<{ payment_plan: PaymentPlan }>(`${API}/billing/payment-plans`, data);
  }

  registerInstallment(planId: number, amount?: number): Observable<any> {
    return this.http.post(`${API}/billing/payment-plans/${planId}/installment`, { amount });
  }

  getSummary(): Observable<any> {
    return this.http.get(`${API}/billing/summary`);
  }
}

// ─── Dashboard ──────────────────────────────────────────────────────────────────
@Injectable({ providedIn: 'root' })
export class DashboardService {
  constructor(private http: HttpClient) {}

  getData(): Observable<DashboardData> {
    return this.http.get<DashboardData>(`${API}/dashboard/`);
  }
}

// ─── Users ───────────────────────────────────────────────────────────────────────
@Injectable({ providedIn: 'root' })
export class UserService {
  constructor(private http: HttpClient) {}

  getAll(role?: string): Observable<{ users: User[]; total: number }> {
    const params = role ? new HttpParams().set('role', role) : {};
    return this.http.get<{ users: User[]; total: number }>(`${API}/users/`, { params });
  }

  getDoctors(): Observable<{ doctors: User[] }> {
    return this.http.get<{ doctors: User[] }>(`${API}/users/doctors`);
  }

  create(data: any): Observable<{ user: User }> {
    return this.http.post<{ user: User }>(`${API}/users/`, data);
  }

  update(id: number, data: any): Observable<{ user: User }> {
    return this.http.put<{ user: User }>(`${API}/users/${id}`, data);
  }

  delete(id: number): Observable<any> {
    return this.http.delete(`${API}/users/${id}`);
  }
}

// ─── Appointment Types ─────────────────────────────────────────────────────────
@Injectable({ providedIn: 'root' })
export class AppointmentTypeService {
  constructor(private http: HttpClient) {}

  getAll(): Observable<{ appointment_types: AppointmentTypeItem[] }> {
    return this.http.get<{ appointment_types: AppointmentTypeItem[] }>(`${API}/appointment-types/`);
  }

  getAdmin(): Observable<{ appointment_types: AppointmentTypeItem[] }> {
    return this.http.get<{ appointment_types: AppointmentTypeItem[] }>(`${API}/appointment-types/all`);
  }

  create(data: Partial<AppointmentTypeItem>): Observable<{ appointment_type: AppointmentTypeItem }> {
    return this.http.post<{ appointment_type: AppointmentTypeItem }>(`${API}/appointment-types/`, data);
  }

  update(id: number, data: Partial<AppointmentTypeItem>): Observable<{ appointment_type: AppointmentTypeItem }> {
    return this.http.put<{ appointment_type: AppointmentTypeItem }>(`${API}/appointment-types/${id}`, data);
  }

  delete(id: number): Observable<any> {
    return this.http.delete(`${API}/appointment-types/${id}`);
  }
}

// ─── Consultorios ──────────────────────────────────────────────────────────────
@Injectable({ providedIn: 'root' })
export class ConsultorioService {
  constructor(private http: HttpClient) {}

  getAll(): Observable<{ consultorios: Consultorio[] }> {
    return this.http.get<{ consultorios: Consultorio[] }>(`${API}/consultorios/`);
  }

  create(data: Partial<Consultorio>): Observable<{ consultorio: Consultorio; message: string }> {
    return this.http.post<{ consultorio: Consultorio; message: string }>(`${API}/consultorios/`, data);
  }

  update(id: number, data: Partial<Consultorio>): Observable<{ consultorio: Consultorio }> {
    return this.http.put<{ consultorio: Consultorio }>(`${API}/consultorios/${id}`, data);
  }

  delete(id: number): Observable<any> {
    return this.http.delete(`${API}/consultorios/${id}`);
  }
}
