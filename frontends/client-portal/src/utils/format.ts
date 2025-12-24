export function formatDateTime(dateStr: string): string {
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(dateStr));
  } catch (err) {
    return dateStr;
  }
}

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

export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return "—";
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date(dateStr));
  } catch (err) {
    return String(dateStr);
  }
}
