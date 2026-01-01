import type { TableDensity } from "./useTableDensity";

interface TableDensityToggleProps {
  density: TableDensity;
  onChange: (density: TableDensity) => void;
}

export function TableDensityToggle({ density, onChange }: TableDensityToggleProps) {
  return (
    <div className="table-toolbar">
      <div className="table-density" role="group" aria-label="Table density">
        <span className="table-density__label">Density</span>
        <div className="table-density__controls">
          <button
            type="button"
            className={`table-density__button${density === "compact" ? " is-active" : ""}`}
            onClick={() => onChange("compact")}
          >
            Compact
          </button>
          <button
            type="button"
            className={`table-density__button${density === "comfortable" ? " is-active" : ""}`}
            onClick={() => onChange("comfortable")}
          >
            Comfortable
          </button>
        </div>
      </div>
    </div>
  );
}
