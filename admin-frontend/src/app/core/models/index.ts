export interface PlatformUser {
  id: number;
  clinic_id?: number | null;
  clinic_name?: string | null;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_platform_admin: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: PlatformUser;
}

export type SubscriptionStatus = 'trial' | 'active' | 'past_due' | 'suspended' | 'cancelled';

export interface SubscriptionTier {
  id: number;
  name: string;
  code: string;
  monthly_price: number;
  max_users: number | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Clinic {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  address: string | null;
  phone: string | null;
  logo_url: string | null;
  subscription_tier_id: number | null;
  subscription_tier_name: string | null;
  subscription_status: SubscriptionStatus;
  trial_ends_at: string | null;
  next_payment_due_at: string | null;
  suspended_at: string | null;
  plan_started_at: string | null;
  plan_expires_at: string | null;
  notes: string | null;
  created_at: string;
  user_count?: number;
}

export interface SubscriptionPayment {
  id: number;
  clinic_id: number;
  amount: number;
  payment_date: string;
  period_start: string | null;
  period_end: string | null;
  notes: string | null;
  recorded_by: string | null;
  created_at: string;
}

export interface ClinicDetail {
  clinic: Clinic;
  admins: PlatformUser[];
  payments: SubscriptionPayment[];
  user_count: number;
}

export interface DashboardStats {
  total_clinics: number;
  clinics_by_status: Record<SubscriptionStatus, number>;
  total_users: number;
  total_revenue: number;
  revenue_this_month: number;
  overdue_clinics: Clinic[];
}
