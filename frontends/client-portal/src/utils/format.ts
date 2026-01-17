const STORAGE_KEY = "neft_client_auth";

const getStoredTimezone = (): string | undefined => {
  if (typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as { timezone?: string | null };
    return parsed.timezone ?? undefined;
  } catch (err) {
    return undefined;
  }
};

export function formatDateTime(dateStr: string, timezone?: string | null): string {
  const resolvedTimezone = timezone ?? getStoredTimezone();
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: resolvedTimezone,
    }).format(new Date(dateStr));
  } catch (err) {
    try {
      return new Intl.DateTimeFormat("ru-RU", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(dateStr));
    } catch (fallbackError) {
      return dateStr;
    }
  }
}

export type NumberParts = {
  int: string;
  fraction?: string | null;
};

export const formatNumberParts = (value: number, fractionDigits = 2): NumberParts => {
  const hasFraction = !Number.isInteger(value);
  const digits = hasFraction ? fractionDigits : 0;
  const fixed = value.toFixed(digits);
  const [intRaw, fraction] = fixed.split(".");
  const intPart = intRaw.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return {
    int: intPart,
    fraction: fraction && digits > 0 ? fraction : null,
  };
};

export type MoneyParts = {
  int: string;
  fraction?: string | null;
  currency: string;
};

export const formatMoneyParts = (amount: number | string, currency = "RUB"): MoneyParts | null => {
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(value)) return null;
  const formatter = new Intl.NumberFormat("ru-RU", { style: "currency", currency, currencyDisplay: "symbol" });
  const currencySymbol =
    formatter.formatToParts(value).find((part) => part.type === "currency")?.value ?? currency;
  const fixed = value.toFixed(2);
  const [intRaw, fraction] = fixed.split(".");
  const intPart = intRaw.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return {
    int: intPart,
    fraction,
    currency: currencySymbol,
  };
};

export function formatMoney(amount: number | string, currency = "RUB"): string {
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(value)) return `${amount} ${currency}`;
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency }).format(value);
}

export function formatLiters(quantity?: number | string | null): string {
  if (quantity === undefined || quantity === null) return "—";
  const value = typeof quantity === "string" ? Number(quantity) : quantity;
  if (Number.isNaN(value)) return String(quantity);
  return new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 3 }).format(value);
}

export function formatDate(dateStr?: string | null, timezone?: string | null): string {
  if (!dateStr) return "—";
  const resolvedTimezone = timezone ?? getStoredTimezone();
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      timeZone: resolvedTimezone,
    }).format(new Date(dateStr));
  } catch (err) {
    try {
      return new Intl.DateTimeFormat("ru-RU", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(new Date(dateStr));
    } catch (fallbackError) {
      return String(dateStr);
    }
  }
}
