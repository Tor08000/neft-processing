export type LogisticsOrder = {
  id: string;
  tenant_id: number;
  client_id: string;
  order_type: string;
  status: string;
  vehicle_id?: string | null;
  driver_id?: string | null;
  planned_start_at?: string | null;
  planned_end_at?: string | null;
  actual_start_at?: string | null;
  actual_end_at?: string | null;
  origin_text?: string | null;
  destination_text?: string | null;
  meta?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type LogisticsRoute = {
  id: string;
  order_id: string;
  version: number;
  status: string;
  distance_km?: number | null;
  planned_duration_minutes?: number | null;
  created_at: string;
};

export type LogisticsStop = {
  id: string;
  route_id: string;
  sequence: number;
  stop_type: string;
  name?: string | null;
  address_text?: string | null;
  lat?: number | null;
  lon?: number | null;
  planned_arrival_at?: string | null;
  planned_departure_at?: string | null;
  actual_arrival_at?: string | null;
  actual_departure_at?: string | null;
  status: string;
  fuel_tx_id?: string | null;
  meta?: Record<string, unknown> | null;
};

export type LogisticsEtaSnapshot = {
  id: string;
  order_id: string;
  computed_at: string;
  eta_end_at: string;
  eta_confidence: number;
  method: string;
  inputs?: Record<string, unknown> | null;
  created_at: string;
};

export type LogisticsRouteSnapshot = {
  id: string;
  order_id: string;
  route_id: string;
  provider: string;
  geometry: Array<{ lat: number; lon: number }>;
  distance_km: number;
  eta_minutes?: number | null;
  created_at: string;
};

export type LogisticsNavigatorExplain = {
  id: string;
  route_snapshot_id: string;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type LogisticsTrackingEvent = {
  id: string;
  order_id: string;
  vehicle_id?: string | null;
  driver_id?: string | null;
  event_type: string;
  ts: string;
  lat?: number | null;
  lon?: number | null;
  speed_kmh?: number | null;
  heading_deg?: number | null;
  odometer_km?: number | null;
  stop_id?: string | null;
  status_from?: string | null;
  status_to?: string | null;
  meta?: Record<string, unknown> | null;
};

export type LogisticsInspection = {
  order: LogisticsOrder;
  active_route?: LogisticsRoute | null;
  routes: LogisticsRoute[];
  active_route_stops: LogisticsStop[];
  latest_eta_snapshot?: LogisticsEtaSnapshot | null;
  latest_route_snapshot?: LogisticsRouteSnapshot | null;
  navigator_explains: LogisticsNavigatorExplain[];
  tracking_events_count: number;
  last_tracking_event?: LogisticsTrackingEvent | null;
};
