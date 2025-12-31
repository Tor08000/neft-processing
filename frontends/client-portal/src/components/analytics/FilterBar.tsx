import type { ChangeEvent } from "react";
import { useMemo } from "react";
import { useI18n } from "../../i18n";
import type { DatePreset } from "../../utils/dateRange";

export interface DateFilters {
  preset: DatePreset;
  from: string;
  to: string;
}

interface FilterBarProps {
  filters: DateFilters;
  presets?: Array<{ value: DatePreset; label: string }>;
  onChange: (next: DateFilters) => void;
}

export function FilterBar({ filters, presets, onChange }: FilterBarProps) {
  const { t } = useI18n();

  const presetOptions = useMemo(
    () =>
      presets ?? [
        { value: "7d", label: t("analytics.filters.presets.last7") },
        { value: "30d", label: t("analytics.filters.presets.last30") },
        { value: "mtd", label: t("analytics.filters.presets.mtd") },
        { value: "90d", label: t("analytics.filters.presets.last90") },
        { value: "custom", label: t("analytics.filters.custom") },
      ],
    [presets, t],
  );

  const handleChange = (event: ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
    const { name, value } = event.target;
    if (name === "preset") {
      onChange({ ...filters, preset: value as DatePreset });
      return;
    }
    onChange({ ...filters, [name]: value, preset: "custom" });
  };

  return (
    <div className="filters analytics-filters">
      <div className="filter">
        <label htmlFor="preset">{t("analytics.filters.period")}</label>
        <select id="preset" name="preset" value={filters.preset} onChange={handleChange}>
          {presetOptions.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </select>
      </div>
      <div className="filter">
        <label htmlFor="from">{t("common.from")}</label>
        <input id="from" name="from" type="date" value={filters.from} onChange={handleChange} />
      </div>
      <div className="filter">
        <label htmlFor="to">{t("common.to")}</label>
        <input id="to" name="to" type="date" value={filters.to} onChange={handleChange} />
      </div>
    </div>
  );
}
