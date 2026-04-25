import type { ReactNode } from "react";
import { EmptyState } from "@shared/ui/EmptyState";
import { ErrorState } from "./ErrorState";
import { TableSkeleton } from "./TableSkeleton";
import { TableDensityToggle } from "./TableDensityToggle";
import { useTableDensity } from "./useTableDensity";
import { formatNumberParts } from "../../utils/format";

export interface Column<T> {
  key: string;
  title: string;
  dataIndex?: keyof T;
  render?: (record: T) => ReactNode;
  className?: string;
}

export interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  toolbar?: ReactNode;
  footer?: ReactNode;
  errorState?: {
    title: string;
    description?: string;
    actionLabel?: string;
    actionOnClick?: () => void;
    details?: string;
  };
  emptyState?: {
    title: string;
    description?: string;
    hint?: string;
    icon?: ReactNode;
    primaryAction?: {
      label: string;
      onClick: () => void;
    };
    secondaryAction?: {
      label: string;
      onClick: () => void;
    };
    actionLabel?: string;
    actionOnClick?: () => void;
  };
  emptyMessage?: string;
  onRowClick?: (record: T) => void;
  rowKey?: (row: T) => string;
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
  toolbar,
  footer,
  errorState,
  emptyState,
  emptyMessage,
  onRowClick,
  rowKey,
}: TableProps<T>) {
  const { density, setDensity } = useTableDensity();
  const footerNode = footer ? <div className="table-footer">{footer}</div> : null;
  const header = toolbar ? (
    <div className="surface-toolbar">
      <div className="table-toolbar__content">{toolbar}</div>
      <TableDensityToggle density={density} onChange={setDensity} />
    </div>
  ) : (
    <TableDensityToggle density={density} onChange={setDensity} />
  );

  if (loading) {
    return (
      <div className="table-shell">
        {header}
        <div className={`table-container table-density-${density}`}>
          <div className="table-scroll">
            <table className="table neft-table">
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col.key}>{col.title}</th>
                  ))}
                </tr>
              </thead>
              <TableSkeleton columns={columns.length} />
            </table>
          </div>
        </div>
        {footerNode}
      </div>
    );
  }

  if (errorState) {
    return (
      <div className="table-shell">
        {header}
        <ErrorState
          title={errorState.title}
          description={errorState.description}
          actionLabel={errorState.actionLabel}
          onAction={errorState.actionOnClick}
          details={errorState.details}
        />
        {footerNode}
      </div>
    );
  }

  if (!data.length && (emptyState || emptyMessage)) {
    return (
      <div className="table-shell">
        {header}
        {emptyState ? (
          <EmptyState
            title={emptyState.title}
            description={emptyState.description ?? ""}
            hint={emptyState.hint}
            icon={emptyState.icon}
            primaryAction={
              emptyState.primaryAction ??
              (emptyState.actionLabel && emptyState.actionOnClick
                ? { label: emptyState.actionLabel, onClick: emptyState.actionOnClick }
                : undefined)
            }
            secondaryAction={emptyState.secondaryAction}
          />
        ) : (
          <div className="card state">{emptyMessage}</div>
        )}
        {footerNode}
      </div>
    );
  }

  return (
    <div className="table-shell">
      {header}
      <div className={`table-container table-density-${density}`}>
        <div className="table-scroll">
          <table className="table neft-table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col.key}>{col.title}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row, idx) => (
                <tr
                  key={rowKey ? rowKey(row) : String(idx)}
                  onClick={() => onRowClick?.(row)}
                  style={{ cursor: onRowClick ? "pointer" : "default" }}
                >
                  {columns.map((col) => {
                    const hasNumericClass = col.className?.includes("neft-num");
                    if (col.render) {
                      return (
                        <td key={col.key} className={hasNumericClass ? `neft-num-cell ${col.className ?? ""}` : col.className}>
                          {col.render(row)}
                        </td>
                      );
                    }
                    const value = row[col.dataIndex as keyof T];
                    const isNumber = typeof value === "number";
                    const cellClass = isNumber || hasNumericClass ? `neft-num-cell ${col.className ?? ""}`.trim() : col.className;
                    return (
                      <td key={col.key} className={cellClass}>
                        {isNumber ? renderNumber(value) : (value as ReactNode)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {footerNode}
    </div>
  );
}
