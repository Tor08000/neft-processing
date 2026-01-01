import { formatMoneyParts } from "../../utils/format";

interface MoneyValueProps {
  amount: number | string;
  currency?: string;
  className?: string;
}

export function MoneyValue({ amount, currency = "RUB", className }: MoneyValueProps) {
  const parts = formatMoneyParts(amount, currency);

  if (!parts) {
    return <span className={className}>{String(amount)} {currency}</span>;
  }

  return (
    <span className={`neft-num neft-money ${className ?? ""}`.trim()}>
      <span className="neft-num__int">{parts.int}</span>
      {parts.fraction ? <span className="neft-num__fraction">.{parts.fraction}</span> : null}
      <span className="neft-num__currency"> {parts.currency}</span>
    </span>
  );
}
