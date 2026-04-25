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
import { Loader } from "../../components/Loader/Loader";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { Toast } from "../../components/Toast/Toast";
import { useToast } from "../../components/Toast/useToast";
import { useAdmin } from "../../admin/AdminContext";
import type {
  MarketplaceModerationAuditItem,
  MarketplaceModerationEntityType,
  MarketplaceModerationReasonCode,
  MarketplaceOfferDetail,
  MarketplaceProductCardDetail,
  MarketplaceServiceDetail,
} from "../../types/marketplaceModeration";
import { formatDateTime } from "../../utils/format";
import { describeRuntimeError } from "../../api/runtimeError";
import {
  moderationDetailCopy,
  moderationEntityLabels,
  moderationReasonOptions,
} from "./marketplaceModerationCopy";

const getEntityTitle = (
  entityType: MarketplaceModerationEntityType,
  detail: MarketplaceProductCardDetail | MarketplaceServiceDetail | MarketplaceOfferDetail | undefined,
) => {
  if (!detail) return "";
  if (entityType === "OFFER") {
    const offerDetail = detail as MarketplaceOfferDetail;
    return offerDetail.title_override?.trim() || moderationEntityLabels[entityType];
  }
  const titledDetail = detail as MarketplaceProductCardDetail | MarketplaceServiceDetail;
  return titledDetail.title;
};

const DetailEmptyState: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <EmptyState title={title} description={description} />
);

const AuditTimeline: React.FC<{ items: MarketplaceModerationAuditItem[] }> = ({ items }) => {
  if (!items.length) {
    return (
      <DetailEmptyState
        title={moderationDetailCopy.audit.emptyTitle}
        description={moderationDetailCopy.audit.emptyDescription}
      />
    );
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
            {item.actor_role ? `${moderationDetailCopy.audit.actor}: ${item.actor_role}` : ""}
            {item.actor_user_id ? ` (${item.actor_user_id})` : ""}
          </div>
          <div style={{ marginTop: 8, display: "grid", gap: 4 }}>
            {(item.before_status || item.after_status) && (
              <div>
                {moderationDetailCopy.audit.status}: {item.before_status ?? moderationDetailCopy.values.fallback} →{" "}
                {item.after_status ?? moderationDetailCopy.values.fallback}
              </div>
            )}
            {item.reason_code && (
              <div>
                {moderationDetailCopy.audit.reason}: {item.reason_code}
              </div>
            )}
            {item.comment && (
              <div>
                {moderationDetailCopy.audit.comment}: {item.comment}
              </div>
            )}
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
        <h3 style={{ marginTop: 0 }}>{moderationDetailCopy.rejectModal.title(title)}</h3>
        <label
          htmlFor="moderation-reject-reason"
          style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}
        >
          <span>{moderationDetailCopy.rejectModal.reasonLabel}</span>
          <select
            id="moderation-reject-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value as MarketplaceModerationReasonCode)}
          >
            <option value="">{moderationDetailCopy.rejectModal.reasonPlaceholder}</option>
            {moderationReasonOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="moderation-reject-comment" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>{moderationDetailCopy.rejectModal.commentLabel}</span>
          <textarea
            id="moderation-reject-comment"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            rows={4}
            placeholder={moderationDetailCopy.rejectModal.commentPlaceholder}
            style={{ resize: "vertical" }}
          />
        </label>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
          <button type="button" className="ghost" onClick={onCancel}>
            {moderationDetailCopy.rejectModal.cancel}
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
            {moderationDetailCopy.rejectModal.submit}
          </button>
        </div>
      </div>
    </div>
  );
};

const ProductDetails: React.FC<{ data: MarketplaceProductCardDetail }> = ({ data }) => (
  <div className="card" style={{ display: "grid", gap: 12 }}>
    <div>
      <strong>{moderationDetailCopy.sections.description}</strong>
      <p>{data.description || moderationDetailCopy.values.fallback}</p>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.category}</strong>
      <div>{data.category}</div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.tags}</strong>
      <div>{data.tags.length ? data.tags.join(", ") : moderationDetailCopy.values.fallback}</div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.attributes}</strong>
      <pre>{JSON.stringify(data.attributes, null, 2)}</pre>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.variants}</strong>
      <pre>{JSON.stringify(data.variants, null, 2)}</pre>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.media}</strong>
      {data.media.length ? (
        <ul>
          {data.media.map((item) => (
            <li key={item.attachment_id}>
              {item.bucket}/{item.path}
            </li>
          ))}
        </ul>
      ) : (
        <DetailEmptyState
          title={moderationDetailCopy.empty.mediaTitle}
          description={moderationDetailCopy.empty.mediaDescription}
        />
      )}
    </div>
  </div>
);

const ServiceDetails: React.FC<{ data: MarketplaceServiceDetail }> = ({ data }) => (
  <div className="card" style={{ display: "grid", gap: 12 }}>
    <div>
      <strong>{moderationDetailCopy.sections.description}</strong>
      <p>{data.description || moderationDetailCopy.values.fallback}</p>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.duration}</strong>
      <div>{data.duration_min} min</div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.requirements}</strong>
      <div>{data.requirements || moderationDetailCopy.values.fallback}</div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.locations}</strong>
      {data.locations.length ? (
        <ul>
          {data.locations.map((location) => (
            <li key={location.id}>
              {location.address || location.location_id}{" "}
              {location.is_active ? "" : moderationDetailCopy.values.inactiveSuffix}
            </li>
          ))}
        </ul>
      ) : (
        <DetailEmptyState
          title={moderationDetailCopy.empty.locationsTitle}
          description={moderationDetailCopy.empty.locationsDescription}
        />
      )}
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.schedulePreview}</strong>
      {data.schedule ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div>
            {moderationDetailCopy.sections.rules}: {data.schedule.rules.length}
            <pre>{JSON.stringify(data.schedule.rules, null, 2)}</pre>
          </div>
          <div>
            {moderationDetailCopy.sections.exceptions}: {data.schedule.exceptions.length}
            <pre>{JSON.stringify(data.schedule.exceptions, null, 2)}</pre>
          </div>
        </div>
      ) : (
        <DetailEmptyState
          title={moderationDetailCopy.empty.scheduleTitle}
          description={moderationDetailCopy.empty.scheduleDescription}
        />
      )}
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.media}</strong>
      {data.media.length ? (
        <ul>
          {data.media.map((item) => (
            <li key={item.attachment_id}>
              {item.bucket}/{item.path}
            </li>
          ))}
        </ul>
      ) : (
        <DetailEmptyState
          title={moderationDetailCopy.empty.mediaTitle}
          description={moderationDetailCopy.empty.mediaDescription}
        />
      )}
    </div>
  </div>
);

const OfferDetails: React.FC<{ data: MarketplaceOfferDetail }> = ({ data }) => (
  <div className="card" style={{ display: "grid", gap: 12 }}>
    <div>
      <strong>{moderationDetailCopy.sections.subject}</strong>
      <div>
        {data.subject_type} · {data.subject_id}
      </div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.description}</strong>
      <div>{data.description_override || moderationDetailCopy.values.fallback}</div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.priceModel}</strong>
      <div>{data.price_model}</div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.price}</strong>
      <div>
        {data.price_amount ?? data.price_min ?? moderationDetailCopy.values.fallback} {data.currency}
      </div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.terms}</strong>
      <pre>{JSON.stringify(data.terms, null, 2)}</pre>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.geoScope}</strong>
      <div>{data.geo_scope}</div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.entitlements}</strong>
      <div>{data.entitlement_scope}</div>
    </div>
    <div>
      <strong>{moderationDetailCopy.sections.validityWindow}</strong>
      <div>
        {data.valid_from ? formatDateTime(data.valid_from) : moderationDetailCopy.values.fallback} →{" "}
        {data.valid_to ? formatDateTime(data.valid_to) : moderationDetailCopy.values.fallback}
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
  const { profile } = useAdmin();
  const { toast, showToast } = useToast();
  const [isRejectOpen, setRejectOpen] = useState(false);
  const canApproveMarketplace = Boolean(profile?.permissions?.marketplace?.approve) && !profile?.read_only;

  const isProduct = entityType === "PRODUCT";
  const isService = entityType === "SERVICE";
  const isOffer = entityType === "OFFER";

  const productQuery = useQuery({
    queryKey: ["mp", "moderation", "product", id],
    queryFn: () => {
      if (!id) throw new Error("Missing id");
      return fetchProductCardDetail(id);
    },
    enabled: isProduct && Boolean(id),
  });

  const serviceQuery = useQuery({
    queryKey: ["mp", "moderation", "service", id],
    queryFn: () => {
      if (!id) throw new Error("Missing id");
      return fetchServiceDetail(id);
    },
    enabled: isService && Boolean(id),
  });

  const offerQuery = useQuery({
    queryKey: ["mp", "moderation", "offer", id],
    queryFn: () => {
      if (!id) throw new Error("Missing id");
      return fetchOfferDetail(id);
    },
    enabled: isOffer && Boolean(id),
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
      showToast("success", moderationDetailCopy.toasts.approved);
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationQueue"] });
      if (isProduct) {
        queryClient.invalidateQueries({ queryKey: ["mp", "moderation", "product", id] });
      }
      if (isService) {
        queryClient.invalidateQueries({ queryKey: ["mp", "moderation", "service", id] });
      }
      if (isOffer) {
        queryClient.invalidateQueries({ queryKey: ["mp", "moderation", "offer", id] });
      }
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationAudit", entityType, id] });
    },
    onError: (err) =>
      showToast("error", describeRuntimeError(err, moderationDetailCopy.errors.approve).description),
  });

  const rejectMutation = useMutation({
    mutationFn: (payload: { reason_code: MarketplaceModerationReasonCode; comment: string }) => {
      if (!id) throw new Error("Missing id");
      return rejectMarketplaceEntity(entityType, id, payload);
    },
    onSuccess: () => {
      showToast("success", moderationDetailCopy.toasts.rejected);
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationQueue"] });
      if (isProduct) {
        queryClient.invalidateQueries({ queryKey: ["mp", "moderation", "product", id] });
      }
      if (isService) {
        queryClient.invalidateQueries({ queryKey: ["mp", "moderation", "service", id] });
      }
      if (isOffer) {
        queryClient.invalidateQueries({ queryKey: ["mp", "moderation", "offer", id] });
      }
      queryClient.invalidateQueries({ queryKey: ["marketplaceModerationAudit", entityType, id] });
    },
    onError: (err) =>
      showToast("error", describeRuntimeError(err, moderationDetailCopy.errors.reject).description),
  });

  const detail = productQuery.data ?? serviceQuery.data ?? offerQuery.data;
  const activeQuery = isProduct ? productQuery : isService ? serviceQuery : offerQuery;
  const detailError = activeQuery.error
    ? describeRuntimeError(
        activeQuery.error,
        "Moderation detail owner route returned an internal error. Retry or inspect request metadata below.",
      )
    : null;
  const auditError = auditQuery.error
    ? describeRuntimeError(
        auditQuery.error,
        "Moderation audit owner route returned an internal error. Retry or inspect request metadata below.",
      )
    : null;

  const title = useMemo(() => getEntityTitle(entityType, detail), [detail, entityType]);

  return (
    <div>
      <div className="page-header" style={{ gap: 12, alignItems: "center" }}>
        <div>
          <h1 style={{ marginBottom: 4 }}>{title || moderationDetailCopy.fallbackTitle}</h1>
          {detail ? (
            <div className="muted">
              {moderationDetailCopy.subtitle(entityType, detail.status, detail.partner_id)}
            </div>
          ) : null}
        </div>
        <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
          <button type="button" className="ghost" onClick={() => navigate(-1)}>
            {moderationDetailCopy.actions.back}
          </button>
          {canApproveMarketplace ? (
            <>
              <button
                type="button"
                className="neft-btn-secondary"
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending || rejectMutation.isPending || !detail}
              >
                {moderationDetailCopy.actions.approve}
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() => setRejectOpen(true)}
                disabled={approveMutation.isPending || rejectMutation.isPending || !detail}
                style={{ color: "#dc2626" }}
              >
                {moderationDetailCopy.actions.reject}
              </button>
            </>
          ) : (
            <span className="neft-chip neft-chip-muted">Read-only moderation</span>
          )}
        </div>
        {activeQuery.isFetching && !activeQuery.isLoading ? <Loader label={moderationDetailCopy.loading.detail} /> : null}
      </div>

      <Toast toast={toast} />

      {activeQuery.isLoading ? <Loader label={moderationDetailCopy.loading.detail} /> : null}

      {detailError ? (
        <ErrorState
          title={moderationDetailCopy.errors.detailTitle}
          description={detailError.description}
          actionLabel={moderationDetailCopy.actions.retry}
          onAction={() => {
            void activeQuery.refetch();
          }}
          details={detailError.details}
          requestId={detailError.requestId}
          correlationId={detailError.correlationId}
        />
      ) : null}

      {detail ? (
        <div style={{ display: "grid", gap: 16 }}>
          {entityType === "PRODUCT" && <ProductDetails data={detail as MarketplaceProductCardDetail} />}
          {entityType === "SERVICE" && <ServiceDetails data={detail as MarketplaceServiceDetail} />}
          {entityType === "OFFER" && <OfferDetails data={detail as MarketplaceOfferDetail} />}

          <div className="card" style={{ display: "grid", gap: 12 }}>
            <h3 style={{ margin: 0 }}>{moderationDetailCopy.sections.auditTimeline}</h3>
            {auditQuery.isLoading ? <Loader label={moderationDetailCopy.loading.audit} /> : null}
            {auditError ? (
              <ErrorState
                title={moderationDetailCopy.errors.auditTitle}
                description={auditError.description}
                actionLabel={moderationDetailCopy.actions.retry}
                onAction={() => {
                  void auditQuery.refetch();
                }}
                details={auditError.details}
                requestId={auditError.requestId}
                correlationId={auditError.correlationId}
              />
            ) : (
              <AuditTimeline items={auditQuery.data?.items ?? []} />
            )}
          </div>
        </div>
      ) : null}

      {canApproveMarketplace ? (
        <RejectModal
          open={isRejectOpen}
          title={title || moderationEntityLabels[entityType]}
          onCancel={() => setRejectOpen(false)}
          onConfirm={(payload) => {
            rejectMutation.mutate(payload);
            setRejectOpen(false);
          }}
        />
      ) : null}
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
