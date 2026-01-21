import { CORE_API_BASE, ApiError, UnauthorizedError, ValidationError } from "./http";
import type { AuthSession } from "./types";

const parseFilename = (header: string | null): string | null => {
  if (!header) return null;
  const match = header.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? null;
};

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export type ReportParams = Record<string, string | number | boolean | undefined | null | string[]>;

export async function downloadReportCsv(
  path: string,
  params: ReportParams,
  user: AuthSession | null,
): Promise<void> {
  const url = new URL(`${CORE_API_BASE}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    if (Array.isArray(value)) {
      value.forEach((item) => url.searchParams.append(key, item));
      return;
    }
    url.searchParams.set(key, String(value));
  });

  const token = withToken(user);
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(url.toString(), { headers });
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");

  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (response.status === 422) {
    const details = await response.text().catch(() => "");
    throw new ValidationError("Ошибка валидации", details);
  }
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new ApiError(text || `Request failed with status ${response.status}`, response.status, correlationId);
  }

  const blob = await response.blob();
  const fallback = "report.csv";
  const filename = parseFilename(response.headers.get("Content-Disposition")) ?? fallback;
  const link = document.createElement("a");
  const objectUrl = window.URL.createObjectURL(blob);
  link.href = objectUrl;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(objectUrl);
}
