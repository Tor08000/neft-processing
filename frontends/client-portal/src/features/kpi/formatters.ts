export const formatMoney = (value: number, currency = "RUB"): string =>
  new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);

export const formatPercent = (value: number, digits = 0): string =>
  `${value.toFixed(digits)}%`;

export const formatDeltaPercent = (value: number, digits = 1): string => {
  const sign = value > 0 ? "+" : value < 0 ? "" : "";
  return `${sign}${value.toFixed(digits)}%`;
};

export const formatCount = (value: number): string => new Intl.NumberFormat("ru-RU").format(value);
