import type { AuthSession } from "./types";

export const withToken = (user: AuthSession | null) => {
  return { token: user?.token };
};
