import { request } from "./http";
import type { AdminUser, CreateUserPayload, UpdateUserPayload } from "../types/users";

export async function listUsers(token: string): Promise<AdminUser[]> {
  return request<AdminUser[]>("/v1/admin/users", { method: "GET" }, { token, base: "auth" });
}

export async function createUser(token: string, payload: CreateUserPayload): Promise<AdminUser> {
  return request<AdminUser>(
    "/v1/admin/users",
    { method: "POST", body: JSON.stringify(payload) },
    { token, base: "auth" },
  );
}

export async function updateUser(token: string, id: string, payload: UpdateUserPayload): Promise<AdminUser> {
  return request<AdminUser>(
    `/v1/admin/users/${id}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    { token, base: "auth" },
  );
}
