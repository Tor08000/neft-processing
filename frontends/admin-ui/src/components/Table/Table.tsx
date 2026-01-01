import React from "react";
import { EmptyState } from "../common/EmptyState";
import { TableSkeleton } from "../common/TableSkeleton";
import { TableDensityToggle } from "../common/TableDensityToggle";
import { useTableDensity } from "../common/useTableDensity";
import { formatNumberParts } from "../common/numberFormat";

export interface Column<T> {
  key: string;
  title: string;
  dataIndex?: keyof T;
  render?: (record: T) => React.ReactNode;
  width?: string | number;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  emptyState?: {
    title: string;
    description?: string;
    actionLabel?: string;
    actionOnClick?: () => void;
  };
  emptyMessage?: string;
  skeletonRows?: number;
  onRowClick?: (record: T) => void;
}

const renderNumber = (value: number) => {
  const parts = formatNumberParts(value);
  return (
    <span className="neft-num">
      <span className="neft-num__int">{parts.int}</span>
      {parts.fraction ? <span className="neft-num__fraction">.{parts.fraction}</span> : null}
    </span>
  );
};

export function Table<T>({
  columns,
  data,
  loading,
  emptyState,
  emptyMessage,
  skeletonRows,
  onRowClick,
}: TableProps<T>) {
  const { density, setDensity } = useTableDensity();

  if (loading) {
    return (
      <div className="table-shell">
        <TableDensityToggle density={density} onChange={setDensity} />
        <div className={`table-container table-density-${density}`}>
          <div className="table-scroll">
            <table className="table neft-table">
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col.key} style={{ width: col.width }}>
                      {col.title}
                    </th>
                  ))}
                </tr>
              </thead>
              <TableSkeleton columns={columns.length} rows={skeletonRows} />
            </table>
          </div>
        </div>
      </div>
    );
  }

  if (!data.length && (emptyState || emptyMessage)) {
    return (
      <div className="table-shell">
        <TableDensityToggle density={density} onChange={setDensity} />
        {emptyState ? (
          <EmptyState
            title={emptyState.title}
            description={emptyState.description}
            actionLabel={emptyState.actionLabel}
            actionOnClick={emptyState.actionOnClick}
          />
        ) : (
          <div className="card empty-state">{emptyMessage}</div>
        )}
      </div>
    );
  }

  return (
    <div className="table-shell">
      <TableDensityToggle density={density} onChange={setDensity} />
      <div className={`table-container table-density-${density}`}>
        <div className="table-scroll">
          <table className="table neft-table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col.key} style={{ width: col.width }}>
                    {col.title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row, idx) => (
                <tr
                  key={idx}
                  onClick={() => onRowClick?.(row)}
                  style={{ cursor: onRowClick ? "pointer" : "default" }}
                >
                  {columns.map((col) => {
                    if (col.render) {
                      return <td key={col.key}>{col.render(row)}</td>;
                    }
                    const value = row[col.dataIndex as keyof T];
                    const isNumber = typeof value === "number";
                    return (
                      <td key={col.key} className={isNumber ? "neft-num-cell" : undefined}>
                        {isNumber ? renderNumber(value) : String(value)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
