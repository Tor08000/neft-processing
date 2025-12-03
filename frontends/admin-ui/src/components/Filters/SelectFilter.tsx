import React from "react";

interface Option {
  label: string;
  value: string;
}

interface Props {
  label: string;
  options: Option[];
  value?: string;
  onChange: (value: string) => void;
  allowEmpty?: boolean;
}

export const SelectFilter: React.FC<Props> = ({ label, options, value, onChange, allowEmpty }) => {
  return (
    <div className="filter">
      <span className="label">{label}</span>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {allowEmpty !== false && <option value="">Все</option>}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
};
