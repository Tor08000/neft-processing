import { apiPost } from "./client";

interface LoginResponse {
  access_token: string;
}

export async function login(email: string, password: string): Promise<string> {
  const response = await apiPost<LoginResponse>("/api/auth/api/v1/auth/login", { email, password });
  return response.access_token;
}
