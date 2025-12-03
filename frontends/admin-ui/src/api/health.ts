import { apiGet } from "./client";
import { ServiceHealth } from "../types/health";

export async function fetchHealth(): Promise<ServiceHealth[]> {
  const res = await apiGet<{ status: string }>("/api/v1/health");
  return [
    {
      service: "core-api",
      status: res.status === "ok" ? "ok" : "error",
      details: res,
    },
  ];
}
