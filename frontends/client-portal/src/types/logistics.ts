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

export type TripStatus = "CREATED" | "IN_PROGRESS" | "COMPLETED";

export type TripPoint = {
  label?: string | null;
  lat?: number | null;
  lon?: number | null;
};

export type TripStopType = "START" | "STOP" | "END";

export type TripStop = {
  seq: number;
  type: TripStopType;
  label?: string | null;
  lat?: number | null;
  lon?: number | null;
  planned_at?: string | null;
  actual_at?: string | null;
};

export type RouteDetail = {
  trip_id: string;
  stops: TripStop[];
  distance_km?: number | null;
  eta_minutes?: number | null;
};

export type TripListItem = {
  id: string;
  status: TripStatus;
  title?: string | null;
  vehicle?: { id: string; plate?: string | null } | null;
  driver?: { id: string; name?: string | null } | null;
  start_planned_at?: string | null;
  end_planned_at?: string | null;
  start_actual_at?: string | null;
  end_actual_at?: string | null;
  origin?: TripPoint | null;
  destination?: TripPoint | null;
  updated_at?: string | null;
};

export type TripDetail = TripListItem & {
  route_id?: string | null;
  route?: RouteDetail | null;
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
