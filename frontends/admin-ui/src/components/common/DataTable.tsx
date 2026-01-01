import React from "react";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { TableSkeleton } from "./TableSkeleton";
import { TableDensityToggle } from "./TableDensityToggle";
import { useTableDensity } from "./useTableDensity";
import { formatNumberParts } from "./numberFormat";

export interface DataColumn<T> {
  key: string;
  title: string;
  render?: (row: T) => React.ReactNode;
}

interface DataTableProps<T> {
  data: T[];
  columns: DataColumn<T>[];
  loading?: boolean;
  errorState?: {
    title: string;
    description?: string;
    actionLabel?: string;
    actionOnClick?: () => void;
    details?: string;
  };
  emptyMessage?: string;
  emptyState?: {
    title: string;
    description?: string;
    actionLabel?: string;
    actionOnClick?: () => void;
  };
  onRowClick?: (row: T) => void;
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

export function DataTable<T>({
  data,
  columns,
  loading,
  emptyMessage = "Нет данных",
  errorState,
  emptyState,
  onRowClick,
}: DataTableProps<T>) {
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
                  {columns.map((column) => (
                    <th key={column.key}>{column.title}</th>
                  ))}
                </tr>
              </thead>
              <TableSkeleton columns={columns.length} />
            </table>
          </div>
        </div>
      </div>
    );
  }

  if (errorState) {
    return (
      <div className="table-shell">
        <TableDensityToggle density={density} onChange={setDensity} />
        <ErrorState
          title={errorState.title}
          description={errorState.description}
          actionLabel={errorState.actionLabel}
          onAction={errorState.actionOnClick}
          details={errorState.details}
        />
      </div>
    );
  }

  if (!data.length) {
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
          <div className="table-empty">{emptyMessage}</div>
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
                {columns.map((column) => (
                  <th key={column.key}>{column.title}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row, index) => (
                <tr
                  key={index}
                  onClick={() => onRowClick?.(row)}
                  style={{ cursor: onRowClick ? "pointer" : "default" }}
                >
                  {columns.map((column) => {
                    const value = (row as Record<string, React.ReactNode>)[column.key];
                    const isNumber = typeof value === "number";
                    return (
                      <td key={column.key} className={isNumber ? "neft-num-cell" : undefined}>
                        {column.render
                          ? column.render(row)
                          : isNumber
                            ? renderNumber(value)
                            : value}
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
