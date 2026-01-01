import React from "react";

interface DateRangePickerProps {
  start: string;
  end: string;
  onChange: (next: { start: string; end: string }) => void;
}

export const DateRangePicker: React.FC<DateRangePickerProps> = ({ start, end, onChange }) => {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <input
        type="date"
        className="neft-input"
        value={start}
        onChange={(event) => onChange({ start: event.target.value, end })}
      />
      <span style={{ color: "#64748b" }}>—</span>
      <input
        type="date"
        className="neft-input"
        value={end}
        onChange={(event) => onChange({ start, end: event.target.value })}
      />
    </div>
  );
};
