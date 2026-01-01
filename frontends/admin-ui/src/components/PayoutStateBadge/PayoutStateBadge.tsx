import React from "react";
import { PayoutState } from "../../types/payouts";

export function getPayoutStateVariant(state: PayoutState): string {
  switch (state) {
    case "READY":
      return "warning";
    case "SENT":
      return "warning";
    case "SETTLED":
      return "success";
    case "FAILED":
      return "error";
    case "DRAFT":
    default:
      return "neutral";
  }
}

export const PayoutStateBadge: React.FC<{ state: PayoutState }> = ({ state }) => {
  const variant = getPayoutStateVariant(state);
  return <span className={`neft-badge ${variant}`}>{state}</span>;
};
