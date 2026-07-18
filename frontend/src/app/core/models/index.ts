// ─── User Models ──────────────────────────────────────────────────────────────
export type UserRole = 'admin' | 'doctor' | 'receptionist' | 'assistant' | 'guest';

export interface User {
  id: number;
  clinic_id?: number;
  clinic_name?: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  phone?: string;
  specialty?: string;
  license_number?: string;
  is_active: boolean;
  is_platform_admin?: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

// ─── Patient Models ────────────────────────────────────────────────────────────
export type BloodType = 'A+' | 'A-' | 'B+' | 'B-' | 'AB+' | 'AB-' | 'O+' | 'O-' | 'unknown';

/** Optional medical history questionnaire (antecedentes patológicos / no patológicos). All fields optional. */
export interface MedicalHistory {
  patologicos: Record<string, boolean | string | null | undefined>;
  extracciones: Record<string, boolean | null | undefined>;
  no_patologicos: Record<string, boolean | string | null | undefined>;
}

export interface Patient {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  document_number: string;
  document_type: string;
  date_of_birth?: string;
  age?: number;
  gender?: string;
  phone?: string;
  phone_emergency?: string;
  email?: string;
  address?: string;
  city?: string;
  blood_type?: BloodType;
  allergies?: string;
  medical_notes?: string;
  medical_history?: MedicalHistory;
  is_active: boolean;
  created_at: string;
  total_appointments?: number;
  total_treatments?: number;
  active_treatment_plans?: number;
}

// ─── Appointment Models ────────────────────────────────────────────────────────
export type AppointmentStatus =
  | 'scheduled' | 'confirmed' | 'in_progress'
  | 'completed' | 'cancelled' | 'no_show';

// ─── Appointment Type Catalog ──────────────────────────────────────────────────
export interface AppointmentTypeItem {
  id: number;
  key: string;
  label: string;
  color: string;
  is_active: boolean;
  sort_order: number;
}

// ─── Consultorio Models ────────────────────────────────────────────────────────
export interface Consultorio {
  id: number;
  name: string;
  description?: string;
  color: string;
  is_active: boolean;
}

export interface Appointment {
  id: number;
  patient_id: number;
  patient_name: string;
  doctor_id: number;
  doctor_name: string;
  consultorio_id?: number;
  consultorio_name?: string;
  created_by_id: number;
  scheduled_at: string;
  duration_minutes: number;
  appointment_type: string;
  status: AppointmentStatus;
  treatment_plan_id?: number;
  treatment_plan_name?: string;
  session_number?: number;
  reason?: string;
  notes?: string;
  cancellation_reason?: string;
  created_at: string;
  completed_at?: string;
  has_treatment: boolean;
  has_invoice: boolean;
}

// ─── Treatment Models ──────────────────────────────────────────────────────────
export type TreatmentPlanStatus = 'active' | 'completed' | 'cancelled' | 'on_hold';

/** One medication line in a Treatment's structured recetario (FCLI-11). */
export interface Medication {
  name: string;
  concentration?: string;
  form?: string;
  quantity?: string;
  dosage: string;
  duration?: string;
  indications?: string;
}

export interface Treatment {
  id: number;
  patient_id: number;
  patient_name: string;
  doctor_id: number;
  doctor_name: string;
  appointment_id?: number;
  treatment_plan_id?: number;
  treatment_plan_name?: string;
  diagnosis?: string;
  procedure: string;
  tooth_number?: string;
  tooth_surface?: string;
  description?: string;
  clinical_notes?: string;
  prescriptions?: string;
  next_steps?: string;
  has_prescription: boolean;
  medications?: Medication[];
  prescription_notes?: string;
  performed_at: string;
  created_at: string;
}

/** Header info for the recetario print view — GET /api/clinic/info. */
export interface ClinicInfo {
  name: string;
  address?: string;
  phone?: string;
  logo_url?: string;
  email?: string;
}

/** Clinical photo attached to an appointment (Treatment) or a TreatmentPlan. */
export interface TreatmentImage {
  id: number;
  patient_id: number;
  treatment_id?: number;
  treatment_plan_id?: number;
  uploaded_by_id?: number;
  uploaded_by_name?: string;
  content_type?: string;
  file_size?: number;
  caption?: string;
  /** Relative to environment.apiUrl. Must be fetched with the auth token (bytes are served through an authenticated endpoint, not a public URL). */
  file_url: string;
  created_at: string;
}

export interface TreatmentPlan {
  id: number;
  patient_id: number;
  patient_name: string;
  doctor_id: number;
  doctor_name: string;
  name: string;
  description?: string;
  treatment_type: string;
  status: TreatmentPlanStatus;
  total_sessions?: number;
  completed_sessions: number;
  progress_percentage: number;
  tooth_number?: string;
  start_date?: string;
  estimated_end_date?: string;
  actual_end_date?: string;
  notes?: string;
  has_payment_plan: boolean;
  created_at: string;
  sessions?: Treatment[];
}

// ─── Billing Models ────────────────────────────────────────────────────────────
export type InvoiceStatus = 'pending' | 'partial' | 'paid' | 'cancelled' | 'overdue';
// card/transfer/other are legacy values on existing payments; new payments only offer cash/qr.
export type PaymentMethod = 'cash' | 'qr' | 'card' | 'transfer' | 'other';

export interface InvoiceItem {
  id?: number;
  /** The budget item this line charges; null = ítem adicional (not budgeted). */
  budget_item_id?: number | null;
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  patient_id: number;
  patient_name: string;
  appointment_id?: number;
  /** The budget whose items this comprobante charges; null = unrelated to any. */
  budget_id?: number | null;
  budget_name?: string | null;
  subtotal: number;
  discount: number;
  total: number;
  amount_paid: number;
  balance: number;
  status: InvoiceStatus;
  notes?: string;
  due_date?: string;
  items: InvoiceItem[];
  created_at: string;
}

export interface PaymentPlanInstallment {
  id: number | null;
  payment_plan_id: number;
  amount: number;
  notes?: string;
  total_paid_after?: number | null;
  balance_after?: number | null;
  payment_date: string;
  received_by?: string;
}

export interface Payment {
  id: number;
  invoice_id: number;
  amount: number;
  method: PaymentMethod;
  reference?: string;
  notes?: string;
  payment_date: string;
  received_by: string;
}

export interface PaymentPlan {
  id: number;
  patient_id: number;
  patient_name: string;
  treatment_plan_id: number;
  treatment_plan_name?: string;
  name: string;
  total_amount: number;
  down_payment: number;
  installments: number;
  installment_amount: number;
  paid_installments: number;
  partial_progress_amount: number;
  total_paid: number;
  balance: number;
  progress_percentage: number;
  status: string;
  start_date?: string;
  end_date?: string;
  notes?: string;
  created_at: string;
}

export type BudgetStatus = 'draft' | 'accepted' | 'rejected';

/** How a budget item is being collected. Derived server-side from the item's
 * comprobante — never stored, so cancelling one returns its items to 'pending'
 * on its own. */
export type BudgetItemBillingState = 'pending' | 'billing' | 'paid';

export interface BudgetItem {
  id?: number;
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
  billing_state?: BudgetItemBillingState;
  /** The comprobante holding this item; null while pending. */
  invoice_id?: number | null;
  invoice_number?: string | null;
  invoice_status?: InvoiceStatus | null;
}

export interface Budget {
  id: number;
  patient_id: number;
  patient_name: string;
  treatment_plan_id?: number;
  treatment_plan_name?: string;
  doctor_id?: number;
  doctor_name?: string;
  name: string;
  treatment_type: string;
  tooth_number?: string;
  total_amount: number;
  /** Financing is opt-in (FCLI-16). When false, the whole cita ladder below is
   * null — the budget is paid per item as the treatments happen. */
  use_payment_plan: boolean;
  down_payment: number | null;
  num_citas: number | null;
  cost_per_cita: number | null;
  /** Absent on the list endpoint (which sends items_count + the aggregates
   * instead); always present on GET /billing/budgets/:id. */
  items?: BudgetItem[];
  items_count: number;
  items_subtotal: number;
  /** Item value at budget price by state — NOT money received (a comprobante has
   * a global discount and can be partially paid). Hence "En ítems pagados", never
   * "Cobrado"; the cash lives in GET /billing/summary.
   * Invariant: amount_paid + amount_billed + amount_pending === items_subtotal. */
  amount_paid: number;
  amount_billed: number;
  amount_pending: number;
  /** Derived label, not a BudgetStatus: nothing pending and nothing in billing. */
  is_completed: boolean;
  /** True once any item sits on a live comprobante — financing closes here. */
  has_billing: boolean;
  status: BudgetStatus;
  start_date?: string;
  end_date?: string;
  notes?: string;
  converted_plan_id?: number;
  created_at: string;
}

// ─── Dashboard ─────────────────────────────────────────────────────────────────
export interface DashboardData {
  today: {
    total: number;
    pending: number;
    appointments: Appointment[];
  };
  week: { total: number };
  upcoming_7_days: number;
  active_treatment_plans: number;
  monthly_revenue?: number;
  monthly_pending_balance?: number;
  total_patients?: number;
  new_patients_this_month?: number;
  calendar_appointments: Appointment[];
  appointment_status_breakdown: Record<AppointmentStatus, number>;
}

// ─── Permissions ───────────────────────────────────────────────────────────────
export interface AppPage {
  id: number;
  key: string;
  label: string;
  route: string;
  icon?: string;
  description?: string;
  is_system: boolean;
  sort_order: number;
}

export interface PagePermissions {
  can_view: boolean;
  can_create: boolean;
  can_edit: boolean;
  can_delete: boolean;
}

/** Full matrix: { role: { page_key: PagePermissions } } */
export type PermissionMatrix = Record<string, Record<string, PagePermissions>>;

export interface PermissionMatrixResponse {
  pages: AppPage[];
  roles: string[];
  matrix: PermissionMatrix;
}

export interface MyPermissionsResponse {
  role: UserRole;
  viewable_pages: string[];
  pages: AppPage[];
}

// ─── API Response wrappers ─────────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items?: T[];
  total: number;
  pages?: number;
  current_page?: number;
  per_page?: number;
}

export interface ApiError {
  error: string;
  message?: string;
}
