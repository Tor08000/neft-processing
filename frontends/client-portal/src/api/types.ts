export interface LoginResponse {
  access_token?: string;
  refresh_token?: string;
  token?: string;
  token_type: string;
  expires_in: number;
  email: string;
  subject_type: string;
  client_id?: string | null;
  roles: string[];
}

export interface LoginRequest {
  email: string;
  password: string;
  portal?: "client";
}

export interface MeResponse {
  email: string;
  roles: string[];
  subject: string;
  subject_type: string;
  client_id?: string | null;
}

export interface AuthSession {
  token: string;
  refreshToken?: string;
  email: string;
  roles: string[];
  subjectType: string;
  clientId?: string | null;
  timezone?: string | null;
  expiresAt: number;
}
