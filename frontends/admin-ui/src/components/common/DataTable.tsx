import React from "react";

export interface DataColumn<T> {
  key: string;
  title: string;
  render?: (row: T) => React.ReactNode;
}

interface DataTableProps<T> {
  data: T[];
  columns: DataColumn<T>[];
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({ data, columns, loading, emptyMessage = "Нет данных", onRowClick }: DataTableProps<T>) {
  if (loading) {
    return <div style={{ padding: "12px 0" }}>Загрузка...</div>;
  }

  if (!data.length) {
    return <div style={{ padding: "12px 0", color: "#475569" }}>{emptyMessage}</div>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="table neft-table" style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} style={{ textAlign: "left", padding: "8px", borderBottom: "1px solid #e2e8f0" }}>
                {column.title}
              </th>
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
              {columns.map((column) => (
                <td key={column.key} style={{ padding: "8px", borderBottom: "1px solid #f1f5f9" }}>
                  {column.render
                    ? column.render(row)
                    : (() => {
                        const value = (row as Record<string, React.ReactNode>)[column.key];
                        if (typeof value === "number") {
                          return <span className="neft-num">{value}</span>;
                        }
                        return value;
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
