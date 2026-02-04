import React from "react";
import { EmptyState } from "../EmptyState";

export type ChartFrameProps = {
  title: string;
  subtitle?: string;
  height?: number;
  isEmpty: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  onRefresh?: () => void;
  action?: React.ReactNode;
  children: React.ReactNode;
};

export function ChartFrame({
  title,
  subtitle,
  height = 280,
  isEmpty,
  emptyTitle = "Нет данных",
  emptyDescription = "За выбранный период данные отсутствуют.",
  onRefresh,
  action,
  children,
}: ChartFrameProps) {
  return (
    <div className="neft-chart-frame">
      <div className="neft-chart-header">
        <div>
          <div className="neft-chart-title">{title}</div>
          {subtitle ? <div className="neft-chart-subtitle">{subtitle}</div> : null}
        </div>
        {action ? <div>{action}</div> : null}
      </div>

      <div style={{ height, overflow: "auto" }}>
        {isEmpty ? (
          <div className="neft-chart-empty">
            <EmptyState
              title={emptyTitle}
              description={emptyDescription}
              primaryAction={onRefresh ? { label: "Обновить", onClick: onRefresh } : undefined}
            />
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

export default ChartFrame;
