import { apiGet } from "./client";
import { ServiceHealth } from "../types/health";

export async function fetchHealth(): Promise<ServiceHealth[]> {
  return apiGet("/admin/health");
}
