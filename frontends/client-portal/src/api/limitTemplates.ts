import { request } from "./http";
import type { AuthSession } from "./types";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export type LimitTemplateLimit = {
  type: string;
  value: number;
  window: string;
};

export type LimitTemplate = {
  id: string;
  org_id: string;
  name: string;
  description?: string | null;
  limits: LimitTemplateLimit[];
  status: string;
  created_at: string;
};

export async function fetchLimitTemplates(user: AuthSession | null): Promise<LimitTemplate[]> {
  const response = await request<{ items: LimitTemplate[] }>(
    "/client/limits/templates",
    { method: "GET" },
    withToken(user),
  );
  return response.items;
}

export async function createLimitTemplate(
  payload: { name: string; description?: string | null; limits: LimitTemplateLimit[] },
  user: AuthSession | null,
): Promise<LimitTemplate> {
  return request<LimitTemplate>(
    "/client/limits/templates",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );
}

export async function updateLimitTemplate(
  templateId: string,
  payload: { name?: string; description?: string | null; limits?: LimitTemplateLimit[]; status?: string },
  user: AuthSession | null,
): Promise<LimitTemplate> {
  return request<LimitTemplate>(
    `/client/limits/templates/${templateId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    withToken(user),
  );
}
