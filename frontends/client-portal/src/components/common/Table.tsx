import type { ReactNode } from "react";
import { EmptyState } from "../EmptyState";
import { TableSkeleton } from "./TableSkeleton";

export interface Column<T> {
  key: string;
  title: string;
  dataIndex?: keyof T;
  render?: (record: T) => ReactNode;
  className?: string;
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
  onRowClick?: (record: T) => void;
}

export function Table<T>({ columns, data, loading, emptyState, emptyMessage, onRowClick }: TableProps<T>) {
  if (loading) {
    return (
      <div className="table-container">
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
    );
  }

  if (!data.length && (emptyState || emptyMessage)) {
    if (emptyState) {
      return (
        <EmptyState
          title={emptyState.title}
          description={emptyState.description ?? ""}
          actionLabel={emptyState.actionLabel}
          actionOnClick={emptyState.actionOnClick}
        />
      );
    }
    return <div className="card state">{emptyMessage}</div>;
  }

  return (
    <div className="table-container">
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
              key={idx}
              onClick={() => onRowClick?.(row)}
              style={{ cursor: onRowClick ? "pointer" : "default" }}
            >
              {columns.map((col) => (
                <td key={col.key} className={col.className}>
                  {col.render
                    ? col.render(row)
                    : (() => {
                        const value = row[col.dataIndex as keyof T];
                        if (typeof value === "number") {
                          return <span className="neft-num">{value}</span>;
                        }
                        return value as ReactNode;
                      })()}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
