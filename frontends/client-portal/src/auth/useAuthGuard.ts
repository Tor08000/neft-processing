import { useCallback } from "react";
import { ApiError, UnauthorizedError } from "../api/http";
import { getClientMe } from "../api/client";
import type { AuthSession } from "../api/types";

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

export function useAuthGuard() {
  const guard = useCallback(async (user: AuthSession | null) => {
    try {
      return await getClientMe(user);
    } catch (error) {
      if (error instanceof TypeError) {
        await sleep(400);
        return getClientMe(user);
      }
      throw error;
    }
  }, []);

  const classifyGuardError = useCallback((error: unknown): "unauthorized" | "forbidden" | "error" => {
    if (error instanceof UnauthorizedError) {
      return "unauthorized";
    }
    if (error instanceof ApiError && error.status === 403) {
      return "forbidden";
    }
    return "error";
  }, []);

  return { guard, classifyGuardError };
}
