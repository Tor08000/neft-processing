import { request } from "./http";
import type { AdminUser, CreateUserPayload, UpdateUserPayload } from "../types/users";

export async function listUsers(token: string): Promise<AdminUser[]> {
  return request<AdminUser[]>("/admin/users", { method: "GET" }, token);
}

export async function createUser(token: string, payload: CreateUserPayload): Promise<AdminUser> {
  return request<AdminUser>("/admin/users", { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function updateUser(token: string, id: string, payload: UpdateUserPayload): Promise<AdminUser> {
  return request<AdminUser>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
}
