import React, { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import {
  approveMarketplaceEntity,
  fetchModerationAudit,
  fetchOfferDetail,
  fetchProductCardDetail,
  fetchServiceDetail,
  rejectMarketplaceEntity,
} from "../../api/marketplaceModeration";
import type {
  MarketplaceModerationAuditItem,
  MarketplaceModerationEntityType,
  MarketplaceModerationReasonCode,
  MarketplaceOfferDetail,
  MarketplaceProductCardDetail,
  MarketplaceServiceDetail,
} from "../../types/marketplaceModeration";
import { formatDateTime } from "../../utils/format";
import { Loader } from "../../components/Loader/Loader";
import { Toast } from "../../components/Toast/Toast";
import { useToast } from "../../components/Toast/useToast";

const reasonOptions: Array<{ value: MarketplaceModerationReasonCode; label: string }> = [
  { value: "INVALID_CONTENT", label: "Invalid content" },
  { value: "MISSING_INFO", label: "Missing info" },
  { value: "POLICY_VIOLATION", label: "Policy violation" },
  { value: "DUPLICATE", label: "Duplicate" },
  { value: "WRONG_CATEGORY", label: "Wrong category" },
  { value: "PRICING_ISSUE", label: "Pricing issue" },
  { value: "GEO_SCOPE_ISSUE", label: "Geo scope issue" },
  { value: "ENTITLEMENTS_ISSUE", label: "Entitlements issue" },
  { value: "OTHER", label: "Other" },
];

const AuditTimeline: React.FC<{ items: MarketplaceModerationAuditItem[] }> = ({ items }) => {
  if (!items.length) {
    return <div className="muted">Нет событий модерации.</div>;
  }
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
      {items.map((item) => (
        <li key={item.id} className="card" style={{ padding: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <strong>{item.action}</strong>
            <span className="muted">{formatDateTime(item.created_at)}</span>
          </div>
          <div className="muted" style={{ marginTop: 4 }}>
            {item.actor_role ? `Actor: ${item.actor_role}` : ""}{item.actor_user_id ? ` (${item.actor_user_id})` : ""}
          </div>
          <div style={{ marginTop: 8, display: "grid", gap: 4 }}>
            {(item.before_status || item.after_status) && (
              <div>
                Status: {item.before_status ?? "—"} → {item.after_status ?? "—"}
              </div>
            )}
            {item.reason_code && <div>Reason: {item.reason_code}</div>}
            {item.comment && <div>Comment: {item.comment}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
};

interface RejectModalProps {
  open: boolean;
  title: string;
  onConfirm: (payload: { reason_code: MarketplaceModerationReasonCode; comment: string }) => void;
  onCancel: () => void;
}

const RejectModal: React.FC<RejectModalProps> = ({ open, title, onConfirm, onCancel }) => {
  const [reason, setReason] = useState<MarketplaceModerationReasonCode | "">("");
  const [comment, setComment] = useState("");

  const commentTrimmed = comment.trim();
  const canSubmit = Boolean(reason) && commentTrimmed.length >= 10;

  if (!open) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h3 style={{ marginTop: 0 }}>Reject {title}</h3>
        <label style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
          <span>Reason code</span>
          <select value={reason} onChange={(event) => setReason(event.target.value as MarketplaceModerationReasonCode)}>
            <option value="">Select reason</option>
            {reasonOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Comment</span>
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            rows={4}
            placeholder="Укажите причину отклонения (10+ символов)"
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
              if (!reason) return;
              onConfirm({ reason_code: reason, comment: commentTrimmed });
              setReason("");
              setComment("");
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

const ProductDetails: React.FC<{ data: MarketplaceProductCardDetail }> = ({ data }) => (
  <div className="card" style={{ display: "grid", gap: 12 }}>
    <div>
      <strong>Description</strong>
      <p>{data.description || "—"}</p>
    </div>
    <div>
      <strong>Category</strong>
      <div>{data.category}</div>
    </div>
    <div>
      <strong>Tags</strong>
      <div>{data.tags.length ? data.tags.join(", ") : "—"}</div>
    </div>
    <div>
      <strong>Attributes</strong>
      <pre>{JSON.stringify(data.attributes, null, 2)}</pre>
    </div>
    <div>
      <strong>Variants</strong>
      <pre>{JSON.stringify(data.variants, null, 2)}</pre>
    </div>
    <div>
      <strong>Media</strong>
      {data.media.length ? (
        <ul>
          {data.media.map((item) => (
            <li key={item.attachment_id}>
              {item.bucket}/{item.path}
            </li>
          ))}
        </ul>
      ) : (
        <div className="muted">Нет медиа.</div>
      )}
    </div>
  </div>
);

const ServiceDetails: React.FC<{ data: MarketplaceServiceDetail }> = ({ data }) => (
  <div className="card" style={{ display: "grid", gap: 12 }}>
    <div>
      <strong>Description</strong>
      <p>{data.description || "—"}</p>
    </div>
    <div>
      <strong>Duration</strong>
      <div>{data.duration_min} min</div>
    </div>
    <div>
      <strong>Requirements</strong>
      <div>{data.requirements || "—"}</div>
    </div>
    <div>
      <strong>Locations</strong>
      {data.locations.length ? (
        <ul>
          {data.locations.map((location) => (
            <li key={location.id}>
              {location.address || location.location_id} {location.is_active ? "" : "(inactive)"}
            </li>
          ))}
        </ul>
      ) : (
        <div className="muted">Нет локаций.</div>
      )}
    </div>
    <div>
      <strong>Schedule preview</strong>
      {data.schedule ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div>
            Rules: {data.schedule.rules.length}
            <pre>{JSON.stringify(data.schedule.rules, null, 2)}</pre>
          </div>
          <div>
            Exceptions: {data.schedule.exceptions.length}
            <pre>{JSON.stringify(data.schedule.exceptions, null, 2)}</pre>
          </div>
        </div>
      ) : (
        <div className="muted">Нет расписания.</div>
      )}
    </div>
    <div>
      <strong>Media</strong>
      {data.media.length ? (
        <ul>
          {data.media.map((item) => (
            <li key={item.attachment_id}>
              {item.bucket}/{item.path}
            </li>
          ))}
        </ul>
      ) : (
        <div className="muted">Нет медиа.</div>
      )}
    </div>
  </div>
);

const OfferDetails: React.FC<{ data: MarketplaceOfferDetail }> = ({ data }) => (
  <div className="card" style={{ display: "grid", gap: 12 }}>
    <div>
      <strong>Subject</strong>
      <div>
        {data.subject_type} · {data.subject_id}
      </div>
    </div>
    <div>
      <strong>Description</strong>
      <div>{data.description_override || "—"}</div>
    </div>
    <div>
      <strong>Price model</strong>
      <div>{data.price_model}</div>
    </div>
    <div>
      <strong>Price</strong>
      <div>
        {data.price_amount ?? data.price_min ?? "—"} {data.currency}
      </div>
    </div>
    <div>
      <strong>Terms</strong>
      <pre>{JSON.stringify(data.terms, null, 2)}</pre>
    </div>
    <div>
      <strong>Geo scope</strong>
      <div>{data.geo_scope}</div>
    </div>
    <div>
      <strong>Entitlements</strong>
      <div>{data.entitlement_scope}</div>
    </div>
    <div>
      <strong>Validity window</strong>
      <div>
        {data.valid_from ? formatDateTime(data.valid_from) : "—"} → {data.valid_to ? formatDateTime(data.valid_to) : "—"}
      </div>
    </div>
  </div>
);

interface ModerationDetailPageProps {
  entityType: MarketplaceModerationEntityType;
}

export const MarketplaceModerationDetailPage: React.FC<ModerationDetailPageProps> = ({ entityType }) => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast, showToast } = useToast();
  const [isRejectOpen, setRejectOpen] = useState(false);

  const detailQuery = useQuery({
    queryKey: ["marketplaceModerationDetail", entityType, id],
    queryFn: () => {
      if (!id) throw new Error("Missing id");
      if (entityType === "PRODUCT") return fetchProductCardDetail(id);
      if (entityType === "SERVICE") return fetchServiceDetail(id);
      return fetchOfferDetail(id);
    },
    enabled: Boolean(id),
  });

  const auditQuery = useQuery({
    queryKey: ["marketplaceModerationAudit", entityType, id],
    queryFn: () => {
      if (!id) throw new Error("Missing id");
      return fetchModerationAudit({ type: entityType, id });
    },
    enabled: Boolean(id),
  });

  const approveMutation = useMutation({
    mutationFn: () => {
      if (!id) throw new Error("Missing id");
      return approveMarketplaceEntity(entityType, id);
    },
    onSuccess: () => {
      showToast("success", "Approved");
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationQueue"] });
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationDetail", entityType, id] });
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationAudit", entityType, id] });
    },
    onError: (err) => showToast("error", err instanceof Error ? err.message : "Ошибка подтверждения"),
  });

  const rejectMutation = useMutation({
    mutationFn: (payload: { reason_code: MarketplaceModerationReasonCode; comment: string }) => {
      if (!id) throw new Error("Missing id");
      return rejectMarketplaceEntity(entityType, id, payload);
    },
    onSuccess: () => {
      showToast("success", "Rejected");
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationQueue"] });
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationDetail", entityType, id] });
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationAudit", entityType, id] });
    },
    onError: (err) => showToast("error", err instanceof Error ? err.message : "Ошибка отклонения"),
  });

  const detail = detailQuery.data as MarketplaceProductCardDetail | MarketplaceServiceDetail | MarketplaceOfferDetail | undefined;

  const title = useMemo(() => {
    if (!detail) return "";
    if (entityType === "OFFER") return (detail as MarketplaceOfferDetail).title_override || "Offer";
    return detail.title;
  }, [detail, entityType]);

  return (
    <div>
      <div className="page-header" style={{ gap: 12, alignItems: "center" }}>
        <div>
          <h1 style={{ marginBottom: 4 }}>{title || "Moderation detail"}</h1>
          {detail && (
            <div className="muted">
              {entityType} · {detail.status} · Partner {detail.partner_id}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
          <button type="button" className="ghost" onClick={() => navigate(-1)}>
            Back
          </button>
          <button
            type="button"
            className="neft-btn-secondary"
            onClick={() => approveMutation.mutate()}
            disabled={approveMutation.isPending || rejectMutation.isPending}
          >
            Approve
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => setRejectOpen(true)}
            disabled={approveMutation.isPending || rejectMutation.isPending}
            style={{ color: "#dc2626" }}
          >
            Reject
          </button>
        </div>
        {detailQuery.isFetching && <Loader label="Обновляем" />}
      </div>

      <Toast toast={toast} />

      {detailQuery.error && <div style={{ color: "#dc2626" }}>{detailQuery.error.message}</div>}

      {detail && (
        <div style={{ display: "grid", gap: 16 }}>
          {entityType === "PRODUCT" && <ProductDetails data={detail as MarketplaceProductCardDetail} />}
          {entityType === "SERVICE" && <ServiceDetails data={detail as MarketplaceServiceDetail} />}
          {entityType === "OFFER" && <OfferDetails data={detail as MarketplaceOfferDetail} />}

          <div className="card" style={{ display: "grid", gap: 12 }}>
            <h3 style={{ margin: 0 }}>Audit timeline</h3>
            {auditQuery.isLoading ? <Loader label="Загружаем историю" /> : null}
            {auditQuery.error ? (
              <div style={{ color: "#dc2626" }}>{auditQuery.error.message}</div>
            ) : (
              <AuditTimeline items={auditQuery.data?.items ?? []} />
            )}
          </div>
        </div>
      )}

      <RejectModal
        open={isRejectOpen}
        title={title || entityType}
        onCancel={() => setRejectOpen(false)}
        onConfirm={(payload) => {
          rejectMutation.mutate(payload);
          setRejectOpen(false);
        }}
      />
    </div>
  );
};

export const MarketplaceModerationProductDetailPage: React.FC = () => (
  <MarketplaceModerationDetailPage entityType="PRODUCT" />
);

export const MarketplaceModerationServiceDetailPage: React.FC = () => (
  <MarketplaceModerationDetailPage entityType="SERVICE" />
);

export const MarketplaceModerationOfferDetailPage: React.FC = () => (
  <MarketplaceModerationDetailPage entityType="OFFER" />
);
