import { useMemo, useState } from "react";
import type { PriceAnalyticsSeriesPoint } from "../types/prices";
import { formatCurrency, formatDate, formatNumber } from "../utils/format";
import { useI18n } from "../i18n";

type MetricKey = "orders" | "revenue";

interface PriceAnalyticsChartsProps {
  series: PriceAnalyticsSeriesPoint[];
}

const buildPath = (points: { x: number; y: number }[]) => {
  if (!points.length) return "";
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
};

export function PriceAnalyticsCharts({ series }: PriceAnalyticsChartsProps) {
  const { t } = useI18n();
  const [metric, setMetric] = useState<MetricKey>("orders");

  const chartData = useMemo(() => {
    if (!series.length) {
      return { points: [], maxValue: 0 };
    }
    const values = series.map((item) => (metric === "orders" ? item.orders_count : item.revenue_total));
    const maxValue = Math.max(...values, 0);
    const width = 640;
    const height = 200;
    const paddingX = 16;
    const paddingY = 24;
    const usableWidth = width - paddingX * 2;
    const usableHeight = height - paddingY * 2;
    const points = series.map((item, index) => {
      const value = metric === "orders" ? item.orders_count : item.revenue_total;
      const x = paddingX + (index / Math.max(series.length - 1, 1)) * usableWidth;
      const y = paddingY + (1 - (maxValue ? value / maxValue : 0)) * usableHeight;
      return { x, y };
    });
    return { points, maxValue };
  }, [series, metric]);

  if (!series.length) {
    return null;
  }

  const lastPoint = series[series.length - 1];

  return (
    <div className="stack">
      <div className="tabs">
        <button type="button" className={`tab ${metric === "orders" ? "tab--active" : ""}`} onClick={() => setMetric("orders")}>
          {t("priceAnalyticsPage.blocks.timeline.orders")}
        </button>
        <button type="button" className={`tab ${metric === "revenue" ? "tab--active" : ""}`} onClick={() => setMetric("revenue")}>
          {t("priceAnalyticsPage.blocks.timeline.revenue")}
        </button>
      </div>
      <svg viewBox="0 0 640 200" role="img" aria-label={t("priceAnalyticsPage.blocks.timeline.chartLabel")} className="analytics-chart">
        <path d={buildPath(chartData.points)} fill="none" stroke="currentColor" strokeWidth="2" />
        {chartData.points.map((point, index) => (
          <circle key={`${point.x}-${point.y}`} cx={point.x} cy={point.y} r={3} fill="currentColor">
            <title>
              {formatDate(series[index].date)} ·{" "}
              {metric === "orders"
                ? formatNumber(series[index].orders_count)
                : formatCurrency(series[index].revenue_total)}
            </title>
          </circle>
        ))}
      </svg>
      <div className="muted">
        {t("priceAnalyticsPage.blocks.timeline.lastPoint")}{" "}
        {metric === "orders" ? formatNumber(lastPoint.orders_count) : formatCurrency(lastPoint.revenue_total)}
      </div>
    </div>
  );
}
