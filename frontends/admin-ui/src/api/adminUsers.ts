import { request } from "./http";
import type { AdminUser, CreateUserPayload, UpdateUserPayload } from "../types/users";

export async function listUsers(token: string): Promise<AdminUser[]> {
  return request<AdminUser[]>("/users", { method: "GET" }, { token, base: "authAdmin" });
}

export async function createUser(token: string, payload: CreateUserPayload): Promise<AdminUser> {
  return request<AdminUser>(
    "/users",
    { method: "POST", body: JSON.stringify(payload) },
    { token, base: "authAdmin" },
  );
}

export async function updateUser(token: string, id: string, payload: UpdateUserPayload): Promise<AdminUser> {
  return request<AdminUser>(
    `/users/${id}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    { token, base: "authAdmin" },
  );
}
