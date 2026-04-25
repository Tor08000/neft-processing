import type {
  MarketplaceModerationEntityType,
  MarketplaceModerationReasonCode,
  MarketplaceModerationStatus,
} from "../../types/marketplaceModeration";

const rowsLabel = (visible: number, total: number) => `Showing ${visible} of ${total}`;

export const moderationTypeOptions: Array<{ value: MarketplaceModerationEntityType; label: string }> = [
  { value: "PRODUCT", label: "Product" },
  { value: "SERVICE", label: "Service" },
  { value: "OFFER", label: "Offer" },
];

export const moderationStatusOptions: MarketplaceModerationStatus[] = [
  "PENDING_REVIEW",
  "DRAFT",
  "ACTIVE",
  "SUSPENDED",
  "ARCHIVED",
];

export const moderationReasonOptions: Array<{ value: MarketplaceModerationReasonCode; label: string }> = [
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

export const moderationEntityLabels: Record<MarketplaceModerationEntityType, string> = {
  PRODUCT: "Product",
  SERVICE: "Service",
  OFFER: "Offer",
};

export const moderationQueueCopy = {
  defaults: {
    status: "PENDING_REVIEW" as MarketplaceModerationStatus,
  },
  header: {
    title: "Marketplace · Moderation",
    subtitle: "Review products, services, and offers from the active moderation queue.",
  },
  loadingLabel: "Refreshing queue",
  errors: {
    title: "Failed to load moderation queue",
  },
  filters: {
    type: "Type",
    status: "Status",
    search: "Search",
    searchPlaceholder: "Title",
    limit: "Limit",
    allTypes: "All",
  },
  columns: {
    type: "Type",
    title: "Title",
    partner: "Partner",
    status: "Status",
    submitted: "Submitted",
    actions: "Actions",
  },
  actions: {
    open: "Open",
    reset: "Reset filters",
    retry: "Retry",
  },
  empty: {
    pristineTitle: "Moderation queue is empty",
    pristineDescription: "There are no pending review items in the current moderation contour.",
    filteredTitle: "Moderation items not found",
    filteredDescription: "Reset filters or broaden the moderation contour.",
  },
  footer: {
    rows: rowsLabel,
  },
  pagination: {
    previous: "◀ Prev",
    next: "Next ▶",
    summary: ({ currentPage, totalPages, total }: { currentPage: number; totalPages: number; total: number }) =>
      `Page ${currentPage} / ${totalPages} (total ${total})`,
  },
} as const;

export const moderationDetailCopy = {
  fallbackTitle: "Moderation detail",
  subtitle: (entityType: MarketplaceModerationEntityType, status: string, partnerId: string) =>
    `${moderationEntityLabels[entityType]} · ${status} · Partner ${partnerId}`,
  loading: {
    detail: "Refreshing detail",
    audit: "Loading audit timeline",
  },
  errors: {
    detailTitle: "Failed to load moderation detail",
    auditTitle: "Failed to load audit timeline",
    approve: "Approval failed",
    reject: "Rejection failed",
  },
  actions: {
    back: "Back",
    approve: "Approve",
    reject: "Reject",
    retry: "Retry",
  },
  toasts: {
    approved: "Approved",
    rejected: "Rejected",
  },
  sections: {
    description: "Description",
    category: "Category",
    tags: "Tags",
    attributes: "Attributes",
    variants: "Variants",
    media: "Media",
    duration: "Duration",
    requirements: "Requirements",
    locations: "Locations",
    schedulePreview: "Schedule preview",
    rules: "Rules",
    exceptions: "Exceptions",
    subject: "Subject",
    priceModel: "Price model",
    price: "Price",
    terms: "Terms",
    geoScope: "Geo scope",
    entitlements: "Entitlements",
    validityWindow: "Validity window",
    auditTimeline: "Audit timeline",
  },
  audit: {
    emptyTitle: "No moderation events yet",
    emptyDescription: "The moderation audit trail has not started for this item.",
    actor: "Actor",
    status: "Status",
    reason: "Reason",
    comment: "Comment",
  },
  rejectModal: {
    title: (title: string) => `Reject ${title}`,
    reasonLabel: "Reason code",
    reasonPlaceholder: "Select reason",
    commentLabel: "Comment",
    commentPlaceholder: "Explain why this item is rejected (10+ characters)",
    cancel: "Cancel",
    submit: "Reject",
  },
  empty: {
    mediaTitle: "No media attached",
    mediaDescription: "The moderation owner did not return media for this item.",
    locationsTitle: "No locations linked",
    locationsDescription: "The service detail has no locations in the current moderation payload.",
    scheduleTitle: "No schedule preview",
    scheduleDescription: "The moderation payload does not include schedule rules or exceptions yet.",
  },
  values: {
    fallback: "—",
    inactiveSuffix: "(inactive)",
  },
} as const;
