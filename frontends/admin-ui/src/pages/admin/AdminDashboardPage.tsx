import React from "react";
import { Link } from "react-router-dom";
import { useAdmin } from "../../admin/AdminContext";
import { ADMIN_SURFACE_LABELS } from "../../admin/access";
import type { AdminPermissionKey } from "../../types/admin";
import { EmptyState } from "@shared/brand/components";
import { adminDashboardCopy } from "./adminKeyPageCopy";

type SurfaceCard = {
  id: string;
  key: AdminPermissionKey;
  label?: string;
  to: string;
  description: string;
};

const SURFACE_CARDS: SurfaceCard[] = [
  { id: "admins", key: "access", to: "/admins", description: "Auth-host admin roster, role levels and access guardrails." },
  { id: "cases", key: "cases", to: "/cases?queue=SUPPORT", description: "Canonical operator inbox for support, disputes and incidents." },
  { id: "finance", key: "finance", to: "/finance", description: "Invoices, payment intakes, payouts and reconciliation inspection." },
  { id: "revenue", key: "revenue", to: "/finance/revenue", description: "Revenue, overdue aging and commercial finance read surface." },
  { id: "commercial", key: "commercial", to: "/commercial", description: "Org commercial state, entitlements and controlled overrides." },
  { id: "crm", key: "crm", to: "/crm/clients", description: "Canonical CRM control plane for clients, contracts and subscriptions." },
  { id: "marketplace", key: "marketplace", to: "/marketplace/moderation", description: "Marketplace moderation queue and review actions." },
  { id: "onboarding", key: "onboarding", to: "/invitations", description: "Client invitation and onboarding operator controls." },
  { id: "ops-overview", key: "ops", label: "Ops overview", to: "/ops", description: "Operator ops overview without synthetic drilldowns." },
  { id: "ops-escalations", key: "ops", label: "Escalations", to: "/ops/escalations", description: "Escalation inbox with ACK / close workflow." },
  { id: "ops-kpi", key: "ops", label: "Ops KPI", to: "/ops/kpi", description: "SLA and primary-reason KPI without fake dashboard cards." },
  { id: "logistics-inspection", key: "ops", label: "Logistics inspection", to: "/logistics/inspection", description: "Logistics order, route and navigator inspection on canonical admin owner." },
  { id: "geo-analytics", key: "ops", label: "Geo Analytics", to: "/geo", description: "Geo analytics on the mounted ops capability envelope." },
  { id: "rules-sandbox", key: "ops", label: "Rules Sandbox", to: "/rules/sandbox", description: "Rules evaluation sandbox with pinned-version loading, empty and error states." },
  { id: "risk-rules", key: "ops", label: "Risk Rules", to: "/risk/rules", description: "Risk rule registry and detail drilldowns on canonical admin owner." },
  { id: "policy-center", key: "ops", label: "Policy Center", to: "/policies", description: "Fleet and finance policy registry with execution evidence." },
  { id: "runtime", key: "runtime", to: "/runtime", description: "Runtime health summary and platform state." },
  { id: "legal-documents", key: "legal", label: "Legal documents", to: "/legal/documents", description: "Legal documents registry and acceptance review." },
  { id: "legal-partners", key: "legal", label: "Legal partners", to: "/legal/partners", description: "Legal partner review and document-linked checks." },
  { id: "audit", key: "audit", to: "/audit", description: "Audit feed and correlation chain visibility." },
];

const ACTION_LABELS = ["read", "operate", "approve", "override", "manage"] as const;
const SURFACE_PRIORITY: Record<AdminPermissionKey, number> = {
  cases: 0,
  finance: 1,
  revenue: 2,
  ops: 3,
  runtime: 4,
  onboarding: 5,
  marketplace: 6,
  commercial: 7,
  crm: 8,
  legal: 9,
  audit: 10,
  access: 11,
};

export const AdminDashboardPage: React.FC = () => {
  const { profile } = useAdmin();
  const permissions = profile?.permissions;
  const readOnly = profile?.read_only ?? false;
  const accessibleCards = SURFACE_CARDS.filter((card) => permissions?.[card.key]?.read).sort(
    (left, right) => SURFACE_PRIORITY[left.key] - SURFACE_PRIORITY[right.key],
  );
  const writableSurfaces = accessibleCards.filter((card) => permissions?.[card.key]?.write).length;
  const approvalLanes = accessibleCards.filter((card) => permissions?.[card.key]?.approve).length;
  const priorityActions = accessibleCards
    .filter((card) => permissions?.[card.key]?.write || card.key === "runtime" || card.key === "audit")
    .slice(0, 5);

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h1>Admin operator console</h1>
          <p className="muted">{adminDashboardCopy.consoleSubtitle}</p>
        </div>
      </div>

      <div className="surface-toolbar">
        <span className="neft-chip neft-chip-info">primary role: {profile?.primary_role_level ?? "—"}</span>
        <span className="neft-chip neft-chip-muted">env: {profile?.env?.name ?? "—"}</span>
        <span className={readOnly ? "neft-chip neft-chip-warn" : "neft-chip neft-chip-ok"}>
          {readOnly ? "read-only" : "writes enabled"}
        </span>
      </div>

      <section className="card">
        <div className="card__header">
          <div>
            <h2>Operator summary</h2>
            <p className="muted">{adminDashboardCopy.summarySubtitle}</p>
          </div>
        </div>
        <div className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-card__title">Primary level</div>
            <div className="kpi-card__value">{profile?.primary_role_level ?? "—"}</div>
            <div className="kpi-card__subvalue">{profile?.role_levels?.join(", ") || "—"}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-card__title">Visible surfaces</div>
            <div className="kpi-card__value">{accessibleCards.length}</div>
            <div className="kpi-card__subvalue">Only mounted canonical admin contours</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-card__title">Write-enabled</div>
            <div className="kpi-card__value">{writableSurfaces}</div>
            <div className="kpi-card__subvalue">Approve lanes: {approvalLanes}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-card__title">Audit guardrails</div>
            <div className="kpi-card__subvalue">
              reason: {profile?.audit_context?.require_reason ? "required" : "optional"} · correlation:{" "}
              {profile?.audit_context?.require_correlation_id ? "required" : "optional"}
            </div>
            <div className={`kpi-card__callout ${readOnly ? "is-problem" : "is-good"}`}>
              {readOnly ? "Portal is currently read-only." : "Operator writes are enabled."}
            </div>
          </div>
        </div>
      </section>

      <section className="card dashboard-widget">
        <div className="card__header">
          <div>
            <h2>Primary operator routes</h2>
            <p className="muted">{adminDashboardCopy.primaryRoutesSubtitle}</p>
          </div>
        </div>
        {priorityActions.length ? (
          <div className="dashboard-actions">
            {priorityActions.map((card, index) => (
              <Link key={card.id} className={index === 0 ? "neft-button neft-btn-primary" : "ghost"} to={card.to}>
                {card.label ?? ADMIN_SURFACE_LABELS[card.key]}
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            title={adminDashboardCopy.primaryRoutesEmptyTitle}
            description={adminDashboardCopy.primaryRoutesEmptyDescription}
          />
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h2>Visible surfaces</h2>
            <p className="muted">{adminDashboardCopy.visibleSurfacesSubtitle}</p>
          </div>
        </div>
        {accessibleCards.length === 0 ? (
          <EmptyState
            title={adminDashboardCopy.visibleSurfacesEmptyTitle}
            description={adminDashboardCopy.visibleSurfacesEmptyDescription}
          />
        ) : (
          <div className="dashboard-grid">
            {accessibleCards.map((card) => (
              <Link key={card.id} to={card.to} className="card dashboard-widget" style={{ color: "inherit", textDecoration: "none" }}>
                <div className="card__header">
                  <div>
                    <h3>{card.label ?? ADMIN_SURFACE_LABELS[card.key]}</h3>
                    <p className="muted">{card.description}</p>
                  </div>
                  <span className="neft-chip neft-chip-muted">{card.key}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h2>Capability visibility map</h2>
            <p className="muted">Read / operate / approve / override / manage resolved from the canonical admin profile, not from hidden aliases.</p>
          </div>
        </div>
        <div className="table-shell">
          <div className="table-scroll">
            <table className="neft-table">
              <thead>
                <tr>
                  <th>Surface</th>
                  {ACTION_LABELS.map((action) => (
                    <th key={action}>{action}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(Object.keys(ADMIN_SURFACE_LABELS) as AdminPermissionKey[]).map((key) => {
                  const capability = permissions?.[key];
                  return (
                    <tr key={key}>
                      <td>{ADMIN_SURFACE_LABELS[key]}</td>
                      {ACTION_LABELS.map((action) => (
                        <td key={`${key}-${action}`}>{capability?.[action] ? "Yes" : "—"}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
};

export default AdminDashboardPage;
