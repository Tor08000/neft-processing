import { request } from "./http";

export type StationPriceItem = {
  product_code: string;
  price: number | null;
  currency: string | null;
  updated_at: string | null;
  source: string | null;
};

export type StationPricesResponse = {
  items: StationPriceItem[];
};

export async function getStationPrices(token: string, stationId: string, asOf?: string): Promise<StationPricesResponse> {
  const query = new URLSearchParams();
  if (asOf) {
    query.set("as_of", asOf);
  }

  const search = query.toString();
  const path = `/v1/fuel/stations/${encodeURIComponent(stationId)}/prices${search ? `?${search}` : ""}`;
  const response = await request<StationPricesResponse | StationPriceItem[] | null>(path, { method: "GET" }, { token });

  if (Array.isArray(response)) {
    return { items: response };
  }
  return { items: response?.items ?? [] };
}
