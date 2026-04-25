import React from "react";

interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onChange: (nextOffset: number) => void;
  labels?: {
    previous?: string;
    next?: string;
    summary?: (args: { currentPage: number; totalPages: number; total: number }) => string;
  };
}

export const Pagination: React.FC<PaginationProps> = ({ total, limit, offset, onChange, labels }) => {
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const summary =
    labels?.summary?.({ currentPage, totalPages, total }) ?? `Page ${currentPage} / ${totalPages} (total ${total})`;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <button disabled={!hasPrev} onClick={() => onChange(Math.max(0, offset - limit))}>
        {labels?.previous ?? "◀ Prev"}
      </button>
      <span style={{ fontSize: 14 }}>
        {summary}
      </span>
      <button disabled={!hasNext} onClick={() => onChange(offset + limit)}>
        {labels?.next ?? "Next ▶"}
      </button>
    </div>
  );
};
