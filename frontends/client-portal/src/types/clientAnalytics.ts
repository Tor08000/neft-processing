export interface ClientAnalyticsSummaryResponse {
  period: {
    from: string;
    to: string;
  };
  summary: {
    transactions_count: number;
    total_spend: number;
    total_liters: number | null;
    active_cards: number;
    blocked_cards: number;
    unique_drivers: number;
    open_tickets: number;
    sla_breaches_first: number;
    sla_breaches_resolution: number;
  };
  timeseries: Array<{
    date: string;
    spend: number;
    liters: number | null;
    count: number;
  }>;
  tops: {
    cards: Array<{
      card_id: string;
      label: string;
      spend: number;
      count: number;
      liters: number | null;
    }>;
    drivers: Array<{
      user_id: string;
      label: string;
      spend: number;
      count: number;
    }>;
    stations: Array<{
      station_id: string;
      label: string;
      spend: number;
      count: number;
      liters: number | null;
    }>;
  };
  support: {
    open: number;
    avg_first_response_minutes: number | null;
    avg_resolve_minutes: number | null;
  };
}

export interface ClientAnalyticsDrillTransaction {
  tx_id: string;
  occurred_at: string;
  card_id: string;
  card_label: string;
  driver_user_id: string | null;
  driver_label: string | null;
  amount: number;
  currency: string;
  liters: number | null;
  station: string;
  status: string;
}

export interface ClientAnalyticsDrillResponse {
  items: ClientAnalyticsDrillTransaction[];
  next_cursor: string | null;
}

export interface ClientAnalyticsSupportDrillItem {
  ticket_id: string;
  subject: string;
  status: string;
  priority: string;
  created_at: string;
  first_response_status: string;
  resolution_status: string;
}

export interface ClientAnalyticsSupportDrillResponse {
  items: ClientAnalyticsSupportDrillItem[];
  next_cursor: string | null;
}
