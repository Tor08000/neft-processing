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
