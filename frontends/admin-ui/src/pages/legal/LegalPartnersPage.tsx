import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
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
import { ErrorState } from "../../components/common/ErrorState";
import { describeRuntimeError } from "../../api/runtimeError";

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

  const canRead = Boolean(profile?.permissions.legal?.read);
  const canWrite = Boolean(profile?.permissions.legal?.write) && !profile?.read_only;
  const canUseApi = Boolean(accessToken) && canRead;
  const filtersActive = Boolean(statusFilter || search.trim());

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
    enabled: canUseApi,
    staleTime: 20_000,
    placeholderData: (prev) => prev,
  });

  const { data: detailData, isLoading: detailLoading, error: detailError, refetch: refetchDetail } = useQuery({
    queryKey: ["legal-partner", selectedPartner],
    queryFn: () => fetchLegalPartner(accessToken ?? "", selectedPartner ?? ""),
    enabled: Boolean(canUseApi && selectedPartner),
  });

  if (listError instanceof ApiError && listError.status === 404) {
    return <AdminMisconfigPage requestId={listError.requestId ?? undefined} errorId={listError.errorCode ?? undefined} />;
  }

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const normalizedDetail = normalizeDetail(detailData ?? null);
  const listRuntimeError =
    listError && !(listError instanceof ApiError && listError.status === 404)
      ? describeRuntimeError(listError, "Failed to load partner legal review queue.")
      : null;
  const detailRuntimeError = detailError
    ? describeRuntimeError(detailError, "Failed to load partner legal detail.")
    : null;

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

  if (!canUseApi) {
    return (
      <div className="stack">
        <div className="page-header">
          <div>
            <h1>Legal partners</h1>
            <p className="muted">Canonical partner legal review queue and operator detail surface.</p>
          </div>
        </div>
        <EmptyState
          title="Legal partner review is access-limited"
          description="The current admin profile cannot access the partner legal review owner route."
          hint="Switch to an admin account with legal read permissions."
        />
      </div>
    );
  }

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
        <div>
          <h1>Legal partners</h1>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <Link to="/legal/documents">Documents</Link>
            <Link to="/legal/partners">Partners</Link>
          </div>
        </div>
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

      <Table
        columns={columns}
        data={items}
        loading={isLoading && !data}
        onRowClick={handleSelect}
        errorState={
          listRuntimeError
            ? {
                title: "Failed to load legal partners",
                description: listRuntimeError.description,
                actionLabel: "Retry",
                actionOnClick: () => {
                  void refetch();
                },
                details: listRuntimeError.details,
                requestId: listRuntimeError.requestId,
                correlationId: listRuntimeError.correlationId,
              }
            : undefined
        }
        emptyState={{
          title: filtersActive ? "No partners match the current legal filters" : "Legal partner review queue is empty",
          description: filtersActive
            ? "Broaden the current search or reset the legal review filters."
            : "The owner route is healthy, but no partner is waiting in the legal review queue yet.",
          hint: filtersActive
            ? "Filtered-empty state is scoped only to the current legal review search."
            : "Select a partner once the first legal review record appears in the queue.",
          primaryAction: filtersActive ? { label: "Reset filters", onClick: handleResetFilters } : undefined,
        }}
        footer={<Pagination total={total} limit={limit} offset={offset} onChange={(value) => setOffset(value)} />}
      />

      <section className="card">
        <h2 style={{ marginTop: 0 }}>Partner detail</h2>
        {detailLoading ? (
          <Loader label="Loading partner profile" />
        ) : detailRuntimeError && selectedPartner ? (
          <ErrorState
            title="Failed to load partner detail"
            description={detailRuntimeError.description}
            actionLabel="Retry"
            onAction={() => void refetchDetail()}
            details={detailRuntimeError.details}
            requestId={detailRuntimeError.requestId}
            correlationId={detailRuntimeError.correlationId}
          />
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
                <EmptyState
                  title="No legal documents linked yet"
                  description="The selected partner does not have linked legal documents in the current owner payload."
                />
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
                <EmptyState
                  title="No payout blocks detected"
                  description="The current legal detail payload does not report payout blocks for this partner."
                />
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
          <EmptyState
            title="Choose a partner to review legal detail"
            description="Select any partner from the queue to inspect documents, payout blocks, and the legal profile."
          />
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
