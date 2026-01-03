import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { approveMarketplaceProduct, fetchModerationQueue, rejectMarketplaceProduct } from "../../api/marketplaceModeration";
import type { MarketplaceModerationProduct, MarketplaceModerationStatus } from "../../types/marketplaceModeration";
import { Table, type Column } from "../../components/Table/Table";
import { Pagination } from "../../components/Pagination/Pagination";
import { formatDateTime } from "../../utils/format";
import { Loader } from "../../components/Loader/Loader";
import { useToast } from "../../components/Toast/useToast";
import { Toast } from "../../components/Toast/Toast";

interface RejectModalProps {
  open: boolean;
  product?: MarketplaceModerationProduct | null;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

const RejectModal: React.FC<RejectModalProps> = ({ open, product, onConfirm, onCancel }) => {
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) {
      setReason("");
    }
  }, [open, product?.id]);

  if (!open || !product) return null;

  const canSubmit = reason.trim().length > 0;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h3 style={{ marginTop: 0 }}>Reject {product.title}</h3>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Причина</span>
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={4}
            placeholder="Укажите причину отклонения"
            style={{ resize: "vertical" }}
          />
        </label>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
          <button type="button" className="ghost" onClick={onCancel}>
            Отмена
          </button>
          <button
            type="button"
            onClick={() => {
              onConfirm(reason.trim());
              setReason("");
            }}
            disabled={!canSubmit}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border: "none",
              background: canSubmit ? "#dc2626" : "#cbd5e1",
              color: "#fff",
              fontWeight: 600,
              cursor: canSubmit ? "pointer" : "not-allowed",
            }}
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
};

export const MarketplaceModerationPage: React.FC = () => {
  const [status, setStatus] = useState<MarketplaceModerationStatus>("PENDING_REVIEW");
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [rejectTarget, setRejectTarget] = useState<MarketplaceModerationProduct | null>(null);
  const queryClient = useQueryClient();
  const { toast, showToast } = useToast();

  const queryParams = useMemo(
    () => ({
      status,
      limit,
      offset,
    }),
    [status, limit, offset],
  );

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["marketplaceModerationQueue", queryParams],
    queryFn: () => fetchModerationQueue(queryParams),
    staleTime: 15_000,
    placeholderData: (previousData) => previousData,
  });

  const approveMutation = useMutation({
    mutationFn: (productId: string) => approveMarketplaceProduct(productId),
    onSuccess: () => {
      showToast("success", "Product approved");
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationQueue"] });
    },
    onError: (err) => showToast("error", err instanceof Error ? err.message : "Ошибка подтверждения"),
  });

  const rejectMutation = useMutation({
    mutationFn: ({ productId, reason }: { productId: string; reason: string }) =>
      rejectMarketplaceProduct(productId, reason),
    onSuccess: () => {
      showToast("success", "Product rejected");
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationQueue"] });
    },
    onError: (err) => showToast("error", err instanceof Error ? err.message : "Ошибка отклонения"),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const columns: Column<MarketplaceModerationProduct>[] = [
    { key: "created_at", title: "Создан", render: (row) => (row.created_at ? formatDateTime(row.created_at) : "—") },
    { key: "title", title: "Товар/услуга", render: (row) => row.title },
    { key: "partner", title: "Партнер", render: (row) => row.partner_id },
    { key: "category", title: "Категория", render: (row) => row.category },
    { key: "status", title: "Статус", render: (row) => row.moderation_status },
    {
      key: "actions",
      title: "Действия",
      render: (row) => (
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="neft-btn-secondary"
            onClick={(event) => {
              event.stopPropagation();
              approveMutation.mutate(row.id);
            }}
            disabled={approveMutation.isPending || rejectMutation.isPending}
          >
            Approve
          </button>
          <button
            type="button"
            className="ghost"
            onClick={(event) => {
              event.stopPropagation();
              setRejectTarget(row);
            }}
            disabled={approveMutation.isPending || rejectMutation.isPending}
            style={{ color: "#dc2626" }}
          >
            Reject
          </button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Marketplace → Moderation</h1>
        {(isLoading || isFetching) && <Loader label="Обновляем очередь" />}
        {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
      </div>

      {toast ? <Toast toast={toast} /> : null}

      <div className="filters">
        <div className="filter">
          <span className="label">Статус</span>
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as MarketplaceModerationStatus);
              setOffset(0);
            }}
          >
            <option value="PENDING_REVIEW">PENDING_REVIEW</option>
            <option value="DRAFT">DRAFT</option>
            <option value="APPROVED">APPROVED</option>
            <option value="REJECTED">REJECTED</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">Лимит</span>
          <select
            value={limit}
            onChange={(event) => {
              setLimit(Number(event.target.value));
              setOffset(0);
            }}
          >
            {[10, 20, 50].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Table
        columns={columns}
        data={items}
        loading={isLoading}
        emptyMessage="Очередь модерации пуста"
      />

      <div style={{ marginTop: 12 }}>
        <Pagination total={total} limit={limit} offset={offset} onChange={setOffset} />
      </div>

      <RejectModal
        open={Boolean(rejectTarget)}
        product={rejectTarget}
        onCancel={() => setRejectTarget(null)}
        onConfirm={(reason) => {
          if (!rejectTarget) return;
          rejectMutation.mutate({ productId: rejectTarget.id, reason });
          setRejectTarget(null);
        }}
      />
    </div>
  );
};

export default MarketplaceModerationPage;
