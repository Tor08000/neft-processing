import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { fetchLegalPartner, fetchLegalPartners, updateLegalPartnerStatus } from "../../api/legalPartners";
import type { LegalPartnerDetail, LegalPartnerSummary } from "../../types/legalPartners";
import { Table, type Column } from "../../components/Table/Table";
import { Pagination } from "../../components/Pagination/Pagination";
import { Loader } from "../../components/Loader/Loader";
import AdminWriteActionModal from "../../components/admin/AdminWriteActionModal";
import { useAdmin } from "../../admin/AdminContext";
import { useAuth } from "../../auth/AuthContext";
import { JsonViewer } from "../../components/common/JsonViewer";
import { ApiError } from "../../api/http";
import { AdminMisconfigPage } from "../admin/AdminStatusPages";
import { EmptyState } from "@shared/ui/EmptyState";

type StatusAction = { status: string } | null;

const normalizeDetail = (detail: LegalPartnerDetail | null) => {
  if (!detail) return null;
  return {
    documents: detail.documents ?? [],
    payoutBlocks: detail.payout_blocks ?? [],
    profile: detail.profile ?? detail.raw ?? null,
  };
};

export const LegalPartnersPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { profile } = useAdmin();
  const [searchParams, setSearchParams] = useSearchParams();
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") ?? "");
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [selectedPartner, setSelectedPartner] = useState<string | null>(searchParams.get("partner_id"));
  const [action, setAction] = useState<StatusAction>(null);

  const canWrite = Boolean(profile?.permissions.legal?.write) && !profile?.read_only;

  const filters = useMemo(
    () => ({
      status: statusFilter || undefined,
      search: search || undefined,
      limit,
      offset,
    }),
    [statusFilter, search, limit, offset],
  );

  const {
    data,
    isLoading,
    isFetching,
    error: listError,
    refetch,
  } = useQuery({
    queryKey: ["legal-partners", filters],
    queryFn: () => fetchLegalPartners(accessToken ?? "", filters),
    enabled: Boolean(accessToken),
    staleTime: 20_000,
    placeholderData: (prev) => prev,
  });

  const { data: detailData, isLoading: detailLoading, refetch: refetchDetail } = useQuery({
    queryKey: ["legal-partner", selectedPartner],
    queryFn: () => fetchLegalPartner(accessToken ?? "", selectedPartner ?? ""),
    enabled: Boolean(accessToken && selectedPartner),
  });

  if (listError instanceof ApiError && listError.status === 404) {
    return <AdminMisconfigPage requestId={listError.requestId ?? undefined} errorId={listError.errorCode ?? undefined} />;
  }

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const normalizedDetail = normalizeDetail(detailData ?? null);

  const columns: Column<LegalPartnerSummary>[] = [
    { key: "partner_id", title: "Partner ID", render: (row) => row.partner_id },
    { key: "partner_name", title: "Partner", render: (row) => row.partner_name ?? "—" },
    { key: "legal_status", title: "Status", render: (row) => row.legal_status ?? "—" },
    {
      key: "payout_blocked",
      title: "Payout block",
      render: (row) => (row.payout_blocked ? "Yes" : row.payout_blocked === false ? "No" : "—"),
    },
    { key: "updated_at", title: "Updated", render: (row) => row.updated_at ?? "—" },
  ];

  const handleSelect = (row: LegalPartnerSummary) => {
    setSelectedPartner(row.partner_id);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("partner_id", row.partner_id);
      return next;
    });
  };

  const handleResetFilters = () => {
    setStatusFilter("");
    setSearch("");
    setSelectedPartner(null);
    setOffset(0);
    setSearchParams({});
  };

  const handleStatusUpdate = async ({ reason, correlationId }: { reason: string; correlationId: string }) => {
    if (!accessToken || !selectedPartner || !action) return;
    if (!canWrite) return;
    await updateLegalPartnerStatus(accessToken, selectedPartner, {
      status: action.status,
      reason,
      correlation_id: correlationId,
    });
    setAction(null);
    await Promise.all([refetch(), refetchDetail()]);
  };

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Legal partners</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Loading partners" />}
        </div>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <div className="filter">
          <span className="label">Status</span>
          <input value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} placeholder="status" />
        </div>
        <div className="filter">
          <span className="label">Search</span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="partner id / name" />
        </div>
        <button
          type="button"
          className="ghost"
          onClick={() => setSearchParams({ status: statusFilter, search })}
        >
          Apply
        </button>
      </div>

      {!isLoading && !isFetching && items.length === 0 ? (
        <EmptyState
          title="Нет партнёров"
          description="По текущим фильтрам партнёры не найдены."
          hint="Попробуйте изменить фильтры или запрос."
          primaryAction={{ label: "Сбросить фильтры", onClick: handleResetFilters }}
        />
      ) : (
        <>
          <Table columns={columns} data={items} loading={isLoading} onRowClick={handleSelect} />
          <Pagination total={total} limit={limit} offset={offset} onChange={(value) => setOffset(value)} />
        </>
      )}

      <section className="card">
        <h2 style={{ marginTop: 0 }}>Partner detail</h2>
        {detailLoading ? (
          <Loader label="Loading partner profile" />
        ) : detailData ? (
          <div style={{ display: "grid", gap: 12 }}>
            <div>
              <strong>{detailData.partner_name ?? detailData.partner_id}</strong>
              <div className="muted">Status: {detailData.legal_status ?? "—"}</div>
            </div>
            <div>
              <h3 style={{ marginTop: 0 }}>Documents</h3>
              {normalizedDetail?.documents.length ? (
                <ul>
                  {normalizedDetail.documents.map((doc) => (
                    <li key={doc.id}>
                      {doc.title ?? doc.id} · {doc.status ?? "—"}{" "}
                      {doc.url ? (
                        <a href={doc.url} target="_blank" rel="noreferrer">
                          Open
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="muted">Документы не найдены</div>
              )}
            </div>
            <div>
              <h3 style={{ marginTop: 0 }}>Payout blocks</h3>
              {normalizedDetail?.payoutBlocks.length ? (
                <ul>
                  {normalizedDetail.payoutBlocks.map((block) => (
                    <li key={block}>{block}</li>
                  ))}
                </ul>
              ) : (
                <div className="muted">Блокировки не найдены</div>
              )}
            </div>
            {normalizedDetail?.profile ? (
              <div>
                <h3 style={{ marginTop: 0 }}>Legal profile</h3>
                <JsonViewer value={normalizedDetail.profile} redactionMode="audit" />
              </div>
            ) : null}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="button" className="neft-btn" onClick={() => setAction({ status: "VERIFIED" })} disabled={!canWrite}>
                Verify
              </button>
              <button
                type="button"
                className="neft-btn-secondary"
                onClick={() => setAction({ status: "PENDING_REVIEW" })}
                disabled={!canWrite}
              >
                Review
              </button>
              <button type="button" className="ghost" onClick={() => setAction({ status: "BLOCKED" })} disabled={!canWrite}>
                Block
              </button>
              {!canWrite ? <span className="muted">Read-only mode enabled</span> : null}
            </div>
          </div>
        ) : (
          <div className="muted">Select a partner to view details.</div>
        )}
      </section>

      <AdminWriteActionModal
        isOpen={action !== null}
        title="Confirm legal status change"
        requirePhrase
        confirmPhrase="CONFIRM"
        onConfirm={handleStatusUpdate}
        onCancel={() => setAction(null)}
      />
    </div>
  );
};

export default LegalPartnersPage;
