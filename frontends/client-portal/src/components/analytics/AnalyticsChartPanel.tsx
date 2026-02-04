import type { ReactNode } from "react";
import { ChartFrame } from "@shared/ui/charts/ChartFrame";

interface AnalyticsChartPanelProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  height?: number;
  isEmpty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  onRefresh?: () => void;
  children: ReactNode;
}

export function AnalyticsChartPanel({
  title,
  subtitle,
  action,
  height,
  isEmpty = false,
  emptyTitle,
  emptyDescription,
  onRefresh,
  children,
}: AnalyticsChartPanelProps) {
  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      action={action ? <div className="analytics-panel__action">{action}</div> : null}
      height={height}
      isEmpty={isEmpty}
      emptyTitle={emptyTitle}
      emptyDescription={emptyDescription}
      onRefresh={onRefresh}
    >
      <div className="analytics-panel">{children}</div>
    </ChartFrame>
  );
}
