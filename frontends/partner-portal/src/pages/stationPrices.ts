export const STATION_PRICE_PRODUCTS = ["AI92", "AI95", "DT", "GAS"] as const;

export interface FuelStationPriceApiItem {
  product_code: string;
  price: number;
  currency?: string | null;
  valid_from?: string | null;
  valid_to?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
}

export interface FuelStationPricesResponse {
  station_id: string;
  as_of?: string | null;
  currency?: string | null;
  items: FuelStationPriceApiItem[];
}

export interface StationPriceRow {
  productCode: string;
  price: string;
  currency: string;
  validFrom?: string | null;
  validTo?: string | null;
  updatedAt?: string | null;
  updatedBy?: string | null;
}

export interface StationPricesUpsertPayload {
  source: "MANUAL";
  items: Array<{
    product_code: string;
    price: number;
    currency: string;
    valid_from?: string | null;
    valid_to?: string | null;
  }>;
}

const DECIMAL_3_REGEX = /^\d+(?:[.,]\d{1,3})?$/;

export const mapPricesResponseToRows = (response: FuelStationPricesResponse): StationPriceRow[] =>
  response.items.map((item) => ({
    productCode: item.product_code,
    price: Number(item.price).toFixed(3),
    currency: item.currency ?? response.currency ?? "RUB",
    validFrom: item.valid_from ?? null,
    validTo: item.valid_to ?? null,
    updatedAt: item.updated_at ?? null,
    updatedBy: item.updated_by ?? null,
  }));

export const buildStationPricesPayload = (rows: StationPriceRow[]): StationPricesUpsertPayload => ({
  source: "MANUAL",
  items: rows.map((row) => ({
    product_code: row.productCode,
    price: Number(row.price.replace(",", ".")),
    currency: row.currency,
    valid_from: row.validFrom ?? null,
    valid_to: row.validTo ?? null,
  })),
});

export const validateStationPrice = (value: string): string | null => {
  const trimmed = value.trim();
  if (!trimmed) {
    return "Укажите цену";
  }
  if (!DECIMAL_3_REGEX.test(trimmed)) {
    return "Разрешено не более 3 знаков после запятой";
  }
  const normalized = Number(trimmed.replace(",", "."));
  if (!Number.isFinite(normalized) || normalized <= 0) {
    return "Цена должна быть больше 0";
  }
  return null;
};
