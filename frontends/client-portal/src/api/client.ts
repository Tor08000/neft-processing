import { request } from "./http";
import type { AuthSession } from "./types";

export type ClientMeResponse = {
  user: {
    id: string;
    email: string | null;
    full_name: string | null;
  };
  client: {
    id: string;
    name: string;
  } | null;
  roles: string[];
};

const withToken = (user: AuthSession | null) => ({ token: user?.token, base: "core" as const });

export const getClientMe = (user: AuthSession | null) =>
  request<ClientMeResponse>("/client/v1/me", { method: "GET" }, withToken(user));
