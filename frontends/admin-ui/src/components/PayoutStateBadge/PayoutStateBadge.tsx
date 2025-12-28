import React from "react";
import { PayoutState } from "../../types/payouts";

export function getPayoutStateColor(state: PayoutState): string {
  switch (state) {
    case "READY":
      return "#64748b";
    case "SENT":
      return "#0ea5e9";
    case "SETTLED":
      return "#16a34a";
    case "FAILED":
      return "#dc2626";
    case "DRAFT":
    default:
      return "#94a3b8";
  }
}

export const PayoutStateBadge: React.FC<{ state: PayoutState }> = ({ state }) => {
  const background = getPayoutStateColor(state);
  return (
    <span className="badge" style={{ background, color: "#fff" }}>
      {state}
    </span>
  );
};
