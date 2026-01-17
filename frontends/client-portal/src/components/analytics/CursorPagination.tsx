interface CursorPaginationProps {
  hasMore: boolean;
  isLoading?: boolean;
  onLoadMore: () => void;
}

export function CursorPagination({ hasMore, isLoading, onLoadMore }: CursorPaginationProps) {
  if (!hasMore) return null;

  return (
    <div className="table-footer">
      <div className="muted small">Показаны не все записи.</div>
      <button className="primary" type="button" onClick={onLoadMore} disabled={isLoading}>
        {isLoading ? "Загрузка..." : "Показать ещё"}
      </button>
    </div>
  );
}
