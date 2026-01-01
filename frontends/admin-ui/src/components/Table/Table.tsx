import React from "react";

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
  onRowClick?: (record: T) => void;
}

export function Table<T>({ columns, data, onRowClick }: TableProps<T>) {
  return (
    <div className="table-container">
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
              {columns.map((col) => (
                <td key={col.key}>
                  {col.render ? (
                    col.render(row)
                  ) : (
                    (() => {
                      const value = row[col.dataIndex as keyof T];
                      if (typeof value === "number") {
                        return <span className="neft-num">{value}</span>;
                      }
                      return String(value);
                    })()
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
