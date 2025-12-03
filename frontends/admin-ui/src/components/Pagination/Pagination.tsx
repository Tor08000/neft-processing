import React from "react";

interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onChange: (nextOffset: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({ total, limit, offset, onChange }) => {
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <button disabled={!hasPrev} onClick={() => onChange(Math.max(0, offset - limit))}>
        ◀ Prev
      </button>
      <span style={{ fontSize: 14 }}>
        Page {currentPage} / {totalPages} (total {total})
      </span>
      <button disabled={!hasNext} onClick={() => onChange(offset + limit)}>
        Next ▶
      </button>
    </div>
  );
};
