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


export type TripTrackingPoint = {
  ts: string;
  lat: number;
  lon: number;
  speed_kmh?: number | null;
  heading?: number | null;
  source?: "gps" | "manual" | null;
  accuracy_m?: number | null;
};

export type TripTrackingResponse = {
  trip_id: string;
  items: TripTrackingPoint[];
  last?: TripTrackingPoint | null;
};

export type TripEta = {
  trip_id: string;
  eta_at?: string | null;
  eta_minutes?: number | null;
  updated_at?: string | null;
  method?: "simple" | "provider" | string | null;
  confidence?: number | null;
};

export type TripDeviationType = "LATE_START" | "ROUTE_DEVIATION" | "UNEXPECTED_STOP";

export type TripDeviationSeverity = "INFO" | "WARN" | "CRITICAL";

export type TripSlaImpactLevel = "NONE" | "LOW" | "MEDIUM" | "HIGH";

export type TripDeviationEvidence = {
  planned_at?: string | null;
  actual_at?: string | null;
  delta_minutes?: number | null;
  lat?: number | null;
  lon?: number | null;
  distance_off_route_km?: number | null;
  stop_minutes?: number | null;
};

export type TripSlaImpact = {
  trip_id?: string;
  impact_level: TripSlaImpactLevel;
  signals?: Array<{
    type: TripDeviationType;
    severity?: TripDeviationSeverity;
    delta_minutes?: number | null;
  }>;
  first_response_due_at?: string | null;
  resolve_due_at?: string | null;
  updated_at?: string | null;
  consequence?: string | null;
};

export type TripDeviationEvent = {
  id: string;
  ts: string;
  type: TripDeviationType;
  severity: TripDeviationSeverity;
  title: string;
  details?: string | null;
  evidence?: TripDeviationEvidence | null;
  sla_impact?: TripSlaImpact | null;
};

export type TripDeviationsResponse = {
  trip_id: string;
  items: TripDeviationEvent[];
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

export type FuelLinkReason = "TIME_WINDOW_MATCH" | "ROUTE_PROXIMITY_MATCH" | "STATION_ON_ROUTE" | "MANUAL_LINK";
export type FuelAlertType = "OUT_OF_TIME_WINDOW" | "OUT_OF_ROUTE" | "HIGH_CONSUMPTION";
export type FuelAlertSeverity = "INFO" | "WARN" | "CRITICAL";

export type FuelUnlinkedItem = {
  fuel_tx_id: string;
  ts: string;
  liters: number;
  amount: number;
  station?: string | null;
  best_match_trip?: string | null;
  best_score: number;
  reason: string;
};

export type TripFuelItem = {
  fuel_tx_id: string;
  ts: string;
  liters: number;
  amount: number;
  station?: string | null;
  score: number;
  reason: FuelLinkReason;
};

export type FuelAlertItem = {
  id: string;
  client_id: string;
  trip_id?: string | null;
  fuel_tx_id: string;
  type: FuelAlertType;
  severity: FuelAlertSeverity;
  title: string;
  details?: string | null;
  evidence?: Record<string, unknown> | null;
  status: string;
  created_at: string;
};

export type TripFuelResponse = {
  trip_id: string;
  items: TripFuelItem[];
  totals: { liters: number; amount: number };
  alerts: FuelAlertItem[];
};

export type FuelReportItem = {
  group: string;
  liters: number;
  amount: number;
  tx_count: number;
  alerts_count: number;
};
