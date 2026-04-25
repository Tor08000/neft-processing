import type { ReactNode } from "react";

export type FinanceOverviewTone = "default" | "success" | "warning" | "danger" | "info" | "premium";

export type FinanceOverviewItem = {
  id: string;
  label: ReactNode;
  value: ReactNode;
  meta?: ReactNode;
  action?: ReactNode;
  tone?: FinanceOverviewTone;
};

export type FinanceOverviewProps = {
  items: FinanceOverviewItem[];
  className?: string;
  compact?: boolean;
};

export function FinanceOverview({ items, className, compact = false }: FinanceOverviewProps) {
  return (
    <div className={["finance-overview", compact ? "finance-overview--compact" : "", className].filter(Boolean).join(" ")}>
      {items.map((item) => (
        <div
          key={item.id}
          className={["finance-overview__card", item.tone && item.tone !== "default" ? `is-${item.tone}` : ""]
            .filter(Boolean)
            .join(" ")}
        >
          <div className="finance-overview__label">{item.label}</div>
          <div className="finance-overview__value">{item.value}</div>
          {item.meta ? <div className="finance-overview__meta">{item.meta}</div> : null}
          {item.action ? <div className="finance-overview__action">{item.action}</div> : null}
        </div>
      ))}
    </div>
  );
}

export default FinanceOverview;
