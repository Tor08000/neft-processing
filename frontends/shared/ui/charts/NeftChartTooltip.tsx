import React from "react";

type Row = { label: string; value: string; color?: string };

export function NeftChartTooltip({
  title,
  rows,
}: {
  title: string;
  rows: Row[];
}) {
  return (
    <div className="neft-chart-tooltip">
      <div className="neft-chart-tooltip-title">{title}</div>
      {rows.map((row, index) => (
        <div key={index} className="neft-chart-tooltip-row">
          <div className="neft-chart-tooltip-label">
            {row.color ? <span style={{ color: row.color, marginRight: 8 }}>●</span> : null}
            {row.label}
          </div>
          <div className="neft-chart-tooltip-value">{row.value}</div>
        </div>
      ))}
    </div>
  );
}

export default NeftChartTooltip;
