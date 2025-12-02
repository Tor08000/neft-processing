import React from "react";

interface Props {
  label: string;
  from?: string;
  to?: string;
  onChange: (range: { from?: string; to?: string }) => void;
}

export const DateRangeFilter: React.FC<Props> = ({ label, from, to, onChange }) => {
  return (
    <div className="filter">
      <span className="label">{label}</span>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          type="date"
          value={from || ""}
          onChange={(e) => onChange({ from: e.target.value, to })}
        />
        <input
          type="date"
          value={to || ""}
          onChange={(e) => onChange({ from, to: e.target.value })}
        />
      </div>
    </div>
  );
};
