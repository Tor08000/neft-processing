export type VehicleStatus = "ACTIVE" | "INACTIVE";
export type DriverStatus = "ACTIVE" | "INACTIVE";

export type VehicleDTO = {
  id: string;
  plate: string;
  vin?: string | null;
  make?: string | null;
  model?: string | null;
  fuel_type?: string | null;
  status?: VehicleStatus | null;
  meta?: Record<string, unknown> | null;
};

export type DriverDTO = {
  id: string;
  name: string;
  phone?: string | null;
  status?: DriverStatus | null;
  meta?: Record<string, unknown> | null;
};

export type BindingDTO = {
  id: string;
  vehicle_id: string;
  driver_id: string;
  card_id?: string | null;
  status?: "ACTIVE" | "INACTIVE" | null;
};

export type PaginatedResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};
