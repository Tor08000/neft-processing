import React from "react";
import { PayoutState } from "../../types/payouts";

export function getPayoutStateVariant(state: PayoutState): string {
  switch (state) {
    case "READY":
      return "warn";
    case "SENT":
      return "warn";
    case "SETTLED":
      return "ok";
    case "FAILED":
      return "err";
    case "DRAFT":
    default:
      return "muted";
  }
}

export const PayoutStateBadge: React.FC<{ state: PayoutState }> = ({ state }) => {
  const variant = getPayoutStateVariant(state);
  return <span className={`neft-chip neft-chip-${variant}`}>{state}</span>;
};
