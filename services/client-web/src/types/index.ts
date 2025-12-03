export type ClientRole = "OWNER" | "ADMIN" | "VIEWER";

export interface ClientOrganization {
  id: string;
  name: string;
  inn?: string;
  status: "active" | "blocked";
}

export interface ClientUser {
  id: string;
  email: string;
  fullName: string;
  role: ClientRole;
  status: "active" | "blocked";
  organization: ClientOrganization;
}

export interface Operation {
  id: string;
  date: string;
  type: string;
  status: "success" | "pending" | "failed";
  amount: number;
  fuelType?: string;
  cardRef?: string;
}

export interface Limit {
  id: string;
  type: string;
  period: "day" | "week" | "month";
  amount: number;
  used: number;
}

export interface DashboardSummary {
  totalOperations: number;
  totalAmount: number;
  period: string;
  activeLimits: number;
}
