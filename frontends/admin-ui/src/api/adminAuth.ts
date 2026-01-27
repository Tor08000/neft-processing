import { request } from "./http";

export async function verifyAdminAuth(token: string): Promise<void> {
  await request("/admin/auth/verify", { method: "GET" }, token);
}
