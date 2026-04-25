import { useState, type ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useClient, type PortalError, type PortalState } from "../auth/ClientContext";
import { useAuth } from "../auth/AuthContext";
import { AccessState, resolveAccessState } from "../access/accessState";
import { DemoEmptyState } from "./DemoEmptyState";
import { AppErrorState, AppForbiddenState, AppLoadingState } from "./states";
import { StatusPage } from "./StatusPage";
import { ModuleUnavailablePage } from "../pages/ModuleUnavailablePage";
import { BillingOverdueState } from "./BillingOverdueState";
import { isDemoClient } from "@shared/demo/demo";
import { useClientJourney } from "../auth/ClientJourneyContext";
import { getPlanByCode } from "@shared/subscriptions/catalog";
import { translate } from "../i18n";

type AccessGateProps = {
  capability?: string;
  module?: string;
  requiredRoles?: string[];
  fallbackMode?: "paywall" | "activation" | "forbidden";
  title?: string;
  allowDemoBypass?: boolean;
  children: ReactNode;
};

const DEBUG_ACCESS_GATE = Boolean(import.meta.env.DEV && import.meta.env.VITE_CLIENT_DEBUG_ACCESS_GATE === "true");

const DiagnosticsSummary = ({ error }: { error?: PortalError | null }) => {
  if (!error) return null;
  return (
    <div className="muted small">
      {error.path ? <div>{translate("accessGate.diagnostics.endpoint")}: {error.path}</div> : null}
      {error.status ? <div>{translate("accessGate.diagnostics.status")}: {error.status}</div> : null}
      {error.requestId ? <div>{translate("accessGate.diagnostics.requestId")}: {error.requestId}</div> : null}
    </div>
  );
};

const DiagnosticsDetails = ({ error }: { error?: PortalError | null }) => {
  const [isOpen, setIsOpen] = useState(false);
  if (!error) return null;
  if (!import.meta.env.DEV) {
    return <DiagnosticsSummary error={error} />;
  }
  return (
    <div className="stack">
      <DiagnosticsSummary error={error} />
      <button type="button" className="ghost neft-btn-secondary" onClick={() => setIsOpen((prev) => !prev)}>
        {isOpen ? translate("accessGate.diagnostics.hide") : translate("accessGate.diagnostics.show")}
      </button>
      {isOpen ? (
        <div className="muted small">
          {error.message ? <div>{translate("accessGate.diagnostics.error")}: {error.message}</div> : null}
          {error.kind ? <div>{translate("accessGate.diagnostics.kind")}: {error.kind}</div> : null}
        </div>
      ) : null}
    </div>
  );
};

const PortalStateView = ({
  state,
  error,
  onRetry,
  isDemo,
}: {
  state: PortalState;
  error?: PortalError | null;
  onRetry?: () => void;
  isDemo: boolean;
}) => {
  switch (state) {
    case "AUTH_REQUIRED":
      return <Navigate to="/login" replace />;
    case "FORBIDDEN":
      if (isDemo) return null;
      return (
        <StatusPage
          title={translate("accessGate.portalState.forbidden.title")}
          description={
            <>
              {translate("accessGate.portalState.forbidden.description")}
              <DiagnosticsDetails error={error} />
            </>
          }
          actionLabel={translate("accessGate.portalState.forbidden.action")}
          actionTo="/dashboard"
        />
      );
    case "SERVICE_UNAVAILABLE":
      if (isDemo) return null;
      return (
        <AppErrorState
          message={
            <>
              {translate("accessGate.states.serviceUnavailable")}
              <DiagnosticsDetails error={error} />
            </>
          }
          onRetry={onRetry}
          status={error?.status}
        />
      );
    case "NETWORK_DOWN":
      if (isDemo) return null;
      return (
        <AppErrorState
          message={
            <>
              {translate("accessGate.portalState.networkDown")}
              <DiagnosticsDetails error={error} />
            </>
          }
          onRetry={onRetry}
          status={error?.status}
        />
      );
    case "API_MISCONFIGURED":
      if (isDemo) return null;
      return (
        <AppErrorState
          message={
            <>
              {translate("accessGate.portalState.apiMisconfigured")}
              <DiagnosticsDetails error={error} />
            </>
          }
          onRetry={onRetry}
          status={error?.status}
        />
      );
    case "ERROR_FATAL":
      if (isDemo) return null;
      return (
        <AppErrorState
          message={
            <>
              {error?.message ?? translate("accessGate.portalState.appError")}
              <DiagnosticsDetails error={error} />
            </>
          }
          onRetry={onRetry}
          status={error?.status}
        />
      );
    case "LOADING":
    case "READY":
    default:
      return null;
  }
};


const LimitedCabinetProgress = () => {
  const { state, nextRoute, draft } = useClientJourney();
  const plan = getPlanByCode(draft.selectedPlan);
  const remaining = [
    !draft.selectedPlan ? translate("accessGate.progress.choosePlan") : null,
    !draft.customerType ? translate("accessGate.progress.chooseCustomerType") : null,
    !draft.profileCompleted ? translate("accessGate.progress.completeProfile") : null,
    !draft.signAccepted ? translate("accessGate.progress.acceptSigning") : null,
  ].filter(Boolean);

  return (
    <div className="stack muted small" style={{ marginTop: 8 }}>
      <div>{translate("accessGate.progress.currentStage")}: {state}</div>
      <div>{translate("accessGate.progress.selectedPlan")}: {plan?.title ?? translate("accessGate.progress.notSelected")}</div>
      <div>{translate("accessGate.progress.customerType")}: {draft.customerType ?? translate("accessGate.progress.notSelected")}</div>
      <div>{translate("accessGate.progress.remaining")}: {remaining.length ? remaining.join(" → ") : translate("accessGate.progress.setupComplete")}</div>
      <div>{translate("accessGate.progress.nextStep")}: {nextRoute}</div>
    </div>
  );
};

const AccessStateView = ({
  state,
  title,
  reason,
  requestId,
  correlationId,
  error,
  homePath,
  isDemo = false,
}: {
  state: AccessState;
  title?: string;
  reason?: string | null;
  requestId?: string | null;
  correlationId?: string | null;
  error?: PortalError | null;
  homePath?: string;
  isDemo?: boolean;
}) => {
  const { user } = useAuth();
  const resolvedTitle = title ?? translate("accessGate.defaultTitle");
  const fallbackHome = homePath ?? (user ? "/" : "/login");
  switch (state) {
    case AccessState.NEEDS_ONBOARDING:
      return (
        <StatusPage
          title={translate("accessGate.states.needsOnboarding.title")}
          description={<>{translate("accessGate.states.needsOnboarding.description")}<LimitedCabinetProgress /></>}
          actionLabel={translate("accessGate.states.needsOnboarding.action")}
          actionTo="/onboarding"
        />
      );
    case AccessState.NEEDS_PLAN:
      return (
        <StatusPage
          title={translate("accessGate.states.needsPlan.title")}
          description={<>{translate("accessGate.states.needsPlan.description")}<LimitedCabinetProgress /></>}
          actionLabel={translate("accessGate.states.needsPlan.action")}
          actionTo="/onboarding/plan"
          secondaryAction={
            <Link className="ghost neft-btn-secondary" to="/client/support/new?topic=plan">
              {translate("accessGate.states.needsPlan.secondaryAction")}
            </Link>
          }
        />
      );
    case AccessState.NEEDS_CONTRACT:
      return (
        <StatusPage
          title={translate("accessGate.states.needsContract.title")}
          description={<>{translate("accessGate.states.needsContract.description")}<LimitedCabinetProgress /></>}
          actionLabel={translate("accessGate.states.needsContract.action")}
          actionTo="/onboarding/contract"
        />
      );
    case AccessState.OVERDUE:
      return (
        <StatusPage
          title={translate("accessGate.states.overdue.title")}
          description={translate("accessGate.states.overdue.description")}
          actionLabel={translate("accessGate.states.overdue.action")}
          actionTo="/invoices"
        />
      );
    case AccessState.SUSPENDED:
      return (
        <StatusPage
          title={translate("accessGate.states.suspended.title")}
          description={translate("accessGate.states.suspended.description")}
          actionLabel={translate("accessGate.states.suspended.action")}
          actionTo="/client/support/new?topic=billing"
        />
      );
    case AccessState.LEGAL_PENDING:
      return (
        <StatusPage
          title={translate("accessGate.states.legalPending.title")}
          description={translate("accessGate.states.legalPending.description")}
          actionLabel={translate("accessGate.states.legalPending.action")}
          actionTo="/client/documents"
        />
      );
    case AccessState.PAYOUT_BLOCKED:
      return (
        <StatusPage
          title={translate("accessGate.states.payoutBlocked.title")}
          description={translate("accessGate.states.payoutBlocked.description")}
          actionLabel={translate("accessGate.states.payoutBlocked.action")}
          actionTo="/client/support/new?topic=payout"
        />
      );
    case AccessState.SLA_PENALTY:
      return (
        <StatusPage
          title={translate("accessGate.states.slaPenalty.title")}
          description={translate("accessGate.states.slaPenalty.description")}
          actionLabel={translate("accessGate.states.slaPenalty.action")}
          actionTo="/client/support/new?topic=sla"
        />
      );
    case AccessState.FORBIDDEN_ROLE:
      return <AppForbiddenState message={translate("accessGate.states.forbiddenRole")} />;
    case AccessState.MODULE_DISABLED:
      if (isDemo) {
        return (
          <DemoEmptyState
            title={translate("accessGate.states.demoUnavailable.title")}
            description={translate("accessGate.states.demoUnavailable.description", { title: resolvedTitle })}
            action={
              <Link className="ghost neft-btn-secondary" to="/dashboard">
                {translate("accessGate.states.demoUnavailable.action")}
              </Link>
            }
          />
        );
      }
      return <ModuleUnavailablePage title={resolvedTitle} />;
    case AccessState.MISSING_CAPABILITY:
      if (isDemo) {
        return (
          <DemoEmptyState
            title={translate("accessGate.states.demoUnavailable.title")}
            description={translate("accessGate.states.demoUnavailable.description", { title: resolvedTitle })}
            action={
              <Link className="ghost neft-btn-secondary" to="/dashboard">
                {translate("accessGate.states.demoUnavailable.action")}
              </Link>
            }
          />
        );
      }
      return (
        <StatusPage
          title={translate("accessGate.states.subscriptionLocked.title")}
          description={translate("accessGate.states.subscriptionLocked.description")}
          actionLabel={translate("accessGate.states.subscriptionLocked.action")}
          actionTo="/subscription"
        />
      );
    case AccessState.SERVICE_UNAVAILABLE:
      return (
        <AppErrorState
          message={
            <>
              {translate("accessGate.states.serviceUnavailable")}
              <DiagnosticsDetails error={error} />
              {requestId && requestId !== error?.requestId ? <div>{translate("accessGate.diagnostics.requestId")}: {requestId}</div> : null}
              {correlationId ? <div>{translate("accessGate.diagnostics.correlationId")}: {correlationId}</div> : null}
            </>
          }
          correlationId={correlationId ?? undefined}
        />
      );
    case AccessState.MISCONFIG:
      return (
        <AppErrorState
          message={
            <>
              {translate("accessGate.states.misconfig")}
              <DiagnosticsDetails error={error} />
            </>
          }
          correlationId={correlationId ?? undefined}
        />
      );
    case AccessState.TECH_ERROR:
      return (
        <div className="stack">
          <AppErrorState
            message={
              <>
                {translate("accessGate.states.techError")}
                <DiagnosticsDetails error={error} />
                {reason ? <div>{translate("accessGate.diagnostics.errorId")}: {reason}</div> : null}
              </>
            }
            correlationId={correlationId ?? undefined}
          />
          <div className="actions">
            <Link className="ghost neft-btn-secondary" to={fallbackHome}>
              {translate("accessGate.states.home")}
            </Link>
          </div>
        </div>
      );
    case AccessState.AUTH_REQUIRED:
      return <Navigate to="/login" replace />;
    case AccessState.ACTIVE:
    default:
      return null;
  }
};

export const AccessGate = ({
  capability,
  module,
  requiredRoles,
  fallbackMode = "paywall",
  title,
  allowDemoBypass = true,
  children,
}: AccessGateProps) => {
  const { user } = useAuth();

  const { client, isLoading, error, portalState, refresh } = useClient();
  const location = useLocation();

  if (!user) {
    return null;
  }

  if (portalState === "LOADING" || isLoading) {
    return <AppLoadingState label={translate("accessGate.loading")} />;
  }

  const isDemoClientAccount = isDemoClient(user.email ?? client?.user?.email ?? null);
  const portalView = PortalStateView({
    state: portalState,
    error,
    onRetry: refresh,
    isDemo: allowDemoBypass && isDemoClientAccount,
  });
  if (portalView) {
    return portalView;
  }

  let decision = resolveAccessState({ client, requiredRoles, capability, module });
  if (allowDemoBypass && isDemoClientAccount && decision.state !== AccessState.AUTH_REQUIRED) {
    // Demo-only showcase mode: ignore backend onboarding/entitlement gating and always render routes.
    decision = { state: AccessState.ACTIVE };
  }

  if (DEBUG_ACCESS_GATE) {
    console.info("[access-gate:decision]", {
      route: location.pathname,
      portal_state: portalState,
      access_state: client?.access_state ?? null,
      resolved_state: decision.state,
      is_demo: allowDemoBypass && isDemoClientAccount,
    });
  }

  if (
    (decision.state === AccessState.MISSING_CAPABILITY || decision.state === AccessState.MODULE_DISABLED) &&
    fallbackMode !== "paywall"
  ) {
    decision =
      fallbackMode === "forbidden" ? { state: AccessState.FORBIDDEN_ROLE } : { state: AccessState.NEEDS_ONBOARDING };
  }

  if (decision.state !== AccessState.ACTIVE) {
    if (DEBUG_ACCESS_GATE) {
      console.info("[access-gate:redirect]", {
        route: location.pathname,
        state: decision.state,
      });
    }
    if (decision.state === AccessState.OVERDUE) {
      return <BillingOverdueState billing={client?.billing} />;
    }
    return (
      <AccessStateView
        state={decision.state}
        title={title}
        reason={decision.reason}
        isDemo={allowDemoBypass && isDemoClientAccount}
      />
    );
  }

  return <>{children}</>;
};

export { AccessStateView, PortalStateView };
