import { ApiError, ForbiddenError, UnauthorizedError } from "./http";

export async function verifyAdminAuth(token: string): Promise<void> {
  const response = await fetch("/api/core/admin/auth/verify", {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (response.status === 403) {
    throw new ForbiddenError();
  }
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new ApiError(text || `Request failed with status ${response.status}`, response.status, null, null, null);
  }
}
