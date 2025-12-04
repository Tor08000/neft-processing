export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  email?: string;
  subject_type?: string;
  roles?: string[];
}

export interface MeResponse {
  email: string;
  roles: string[];
  subject: string;
  subject_type: string;
}

export interface AuthUser {
  id: string;
  email: string;
  roles: string[];
  subjectType?: string;
}

export interface AuthSession {
  accessToken: string;
  expiresAt: number;
  email?: string;
  roles?: string[];
}
