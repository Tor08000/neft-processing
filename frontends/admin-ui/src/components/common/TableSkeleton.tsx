import React from "react";

interface TableSkeletonProps {
  rows?: number;
  columns: number;
}

export const TableSkeleton: React.FC<TableSkeletonProps> = ({ rows = 6, columns }) => {
  return (
    <tbody>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={`skeleton-${rowIndex}`} className="table-skeleton__row">
          {Array.from({ length: columns }).map((__, colIndex) => (
            <td key={`skeleton-${rowIndex}-${colIndex}`}>
              <div className="table-skeleton__cell" />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
};
