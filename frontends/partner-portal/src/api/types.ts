export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  email: string;
  subject_type: string;
  partner_id?: string | null;
  roles: string[];
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface MeResponse {
  email: string;
  roles: string[];
  subject: string;
  subject_type: string;
  partner_id?: string | null;
}

export interface AuthSession {
  token: string;
  email: string;
  roles: string[];
  subjectType: string;
  partnerId?: string | null;
  expiresAt: number;
}

export type PartnerRole =
  | "PARTNER_OWNER"
  | "PARTNER_ACCOUNTANT"
  | "PARTNER_OPERATOR"
  | "PARTNER_SERVICE_MANAGER";
