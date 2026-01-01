import type { ReactNode } from "react";

interface TableSkeletonProps {
  rows?: number;
  columns: number;
  cell?: ReactNode;
}

export function TableSkeleton({ rows = 6, columns, cell }: TableSkeletonProps) {
  return (
    <tbody>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={`skeleton-${rowIndex}`} className="table-skeleton__row">
          {Array.from({ length: columns }).map((__, colIndex) => (
            <td key={`skeleton-${rowIndex}-${colIndex}`}>{cell ?? <div className="table-skeleton__cell" />}</td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}
