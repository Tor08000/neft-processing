import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));

describe("admin entrypoint", () => {
  it("mounts the canonical App entry and leaves no legacy router or mock dashboard contour", () => {
    const mainPath = resolve(HERE, "main.tsx");
    const legacyRouterPath = resolve(HERE, "router", "index.tsx");
    const legacyRouterShimPath = resolve(HERE, "router", "router-shim.tsx");
    const legacyDashboardPath = resolve(HERE, "pages", "DashboardPage.tsx");
    const legacyBillingDashboardPath = resolve(HERE, "pages", "BillingDashboardPage.tsx");
    const legacyDashboardTruthTestPath = resolve(HERE, "features", "dashboardRuntimeTruth.test.tsx");
    const legacyKpiHookPath = resolve(HERE, "features", "kpi", "useKpis.ts");
    const legacyAchievementsHookPath = resolve(HERE, "features", "achievements", "useAchievements.ts");
    const legacyLayoutPath = resolve(HERE, "components", "Layout", "Layout.tsx");
    const legacyStubProvidersPagePath = resolve(HERE, "pages", "stubs", "StubProvidersPage.tsx");
    const legacyStubApiPath = resolve(HERE, "api", "stubs.ts");
    const legacyStubTypesPath = resolve(HERE, "types", "stubs.ts");
    const legacyComingSoonPagePath = resolve(HERE, "pages", "admin", "ComingSoonPage.tsx");
    const mainSource = readFileSync(mainPath, "utf8");
    const appSource = readFileSync(resolve(HERE, "App.tsx"), "utf8");
    const shellSource = readFileSync(resolve(HERE, "admin", "AdminShell.tsx"), "utf8");

    expect(mainSource).toContain('import App from "./App";');
    expect(appSource).toContain('import RulesSandboxPage from "./pages/RulesSandboxPage";');
    expect(appSource).toContain('import RiskRulesListPage from "./pages/RiskRulesListPage";');
    expect(appSource).toContain('import RiskRuleDetailsPage from "./pages/RiskRuleDetailsPage";');
    expect(appSource).toContain('import PolicyCenterPage from "./pages/PolicyCenterPage";');
    expect(appSource).toContain('import PolicyCenterDetailPage from "./pages/PolicyCenterDetailPage";');
    expect(appSource).toContain('import RevenuePage from "./pages/finance/RevenuePage";');
    expect(appSource).toContain('path="/rules/sandbox"');
    expect(appSource).toContain('path="/risk/rules"');
    expect(appSource).toContain('path="/risk/rules/:id"');
    expect(appSource).toContain('path="/policies"');
    expect(appSource).toContain('path="/policies/:type/:id"');
    expect(appSource).toContain('path="/finance/revenue"');
    expect(appSource).toContain('permission="revenue"');
    expect(appSource).toContain('permission="ops"');
    expect(shellSource).toContain('label: "Rules Sandbox"');
    expect(shellSource).toContain('to: "/rules/sandbox"');
    expect(shellSource).toContain('label: "Risk Rules"');
    expect(shellSource).toContain('to: "/risk/rules"');
    expect(shellSource).toContain('label: "Policy Center"');
    expect(shellSource).toContain('to: "/policies"');
    expect(shellSource).toContain('label: "Revenue"');
    expect(shellSource).toContain('to: "/finance/revenue"');
    expect(existsSync(legacyRouterPath)).toBe(false);
    expect(existsSync(legacyRouterShimPath)).toBe(false);
    expect(existsSync(legacyDashboardPath)).toBe(false);
    expect(existsSync(legacyBillingDashboardPath)).toBe(false);
    expect(existsSync(legacyDashboardTruthTestPath)).toBe(false);
    expect(existsSync(legacyKpiHookPath)).toBe(false);
    expect(existsSync(legacyAchievementsHookPath)).toBe(false);
    expect(existsSync(legacyLayoutPath)).toBe(false);
    expect(existsSync(legacyStubProvidersPagePath)).toBe(false);
    expect(existsSync(legacyStubApiPath)).toBe(false);
    expect(existsSync(legacyStubTypesPath)).toBe(false);
    expect(existsSync(legacyComingSoonPagePath)).toBe(false);
  });

  it("keeps neighboring unmounted helper surfaces explicitly frozen", () => {
    const appSource = readFileSync(resolve(HERE, "App.tsx"), "utf8");
    const frozenPages = [
      "pages/RiskAnalyticsPage.tsx",
      "pages/OperationsListPage.tsx",
      "pages/OperationDetailsPage.tsx",
      "pages/ExplainPage.tsx",
      "pages/UnifiedExplainPage.tsx",
    ];

    expect(appSource).not.toContain('path="/operations');
    expect(appSource).not.toContain('path="/risk/analytics');
    expect(appSource).not.toContain('path="/explain');
    expect(appSource).not.toContain('path="/unified-explain');

    frozenPages.forEach((relativePath) => {
      const absolutePath = resolve(HERE, relativePath);
      const importPath = `./${relativePath.replace(/\.tsx$/, "")}`;
      expect(existsSync(absolutePath)).toBe(true);
      expect(appSource).not.toContain(importPath);
    });
  });

  it("keeps duplicate finance and billing page families frozen behind canonical /finance routes", () => {
    const appSource = readFileSync(resolve(HERE, "App.tsx"), "utf8");
    const frozenPages = [
      "pages/AccountDetailsPage.tsx",
      "pages/BalancesPage.tsx",
      "pages/BillingSummaryPage.tsx",
      "pages/ClearingBatchesPage.tsx",
      "pages/InvoiceDetailsPage.tsx",
      "pages/InvoicesListPage.tsx",
      "pages/PayoutBatchesPage.tsx",
      "pages/billing/BillingOverviewPage.tsx",
      "pages/billing/BillingInvoicesPage.tsx",
      "pages/billing/BillingInvoiceDetailsPage.tsx",
      "pages/billing/BillingPaymentIntakesPage.tsx",
      "pages/billing/BillingPaymentDetailsPage.tsx",
      "pages/billing/BillingPaymentsPage.tsx",
      "pages/billing/BillingRefundsPage.tsx",
      "pages/billing/BillingLinksPage.tsx",
      "pages/finance/PayoutBatchDetail.tsx",
      "pages/finance/PayoutsList.tsx",
      "pages/money/InvoiceCfoExplainPage.tsx",
      "pages/money/MoneyHealthPage.tsx",
      "pages/money/MoneyReplayPage.tsx",
      "pages/reconciliation/ReconciliationStatementsPage.tsx",
      "pages/reconciliation/ReconciliationRunsPage.tsx",
      "pages/reconciliation/ReconciliationRunDetailsPage.tsx",
      "pages/reconciliation/ReconciliationFixturesPage.tsx",
    ];

    expect(appSource).not.toContain('path="/billing');
    expect(appSource).not.toContain('path="/money');
    expect(appSource).not.toContain('path="/accounts');
    expect(appSource).not.toContain('path="/clearing');
    expect(appSource).not.toContain('path="/reconciliation');

    frozenPages.forEach((relativePath) => {
      const absolutePath = resolve(HERE, relativePath);
      const importPath = `./${relativePath.replace(/\.tsx$/, "")}`;
      expect(existsSync(absolutePath)).toBe(true);
      expect(appSource).not.toContain(importPath);
    });
  });

  it("keeps legacy fleet, subscription, tariff, and partner legal helper pages frozen", () => {
    const appSource = readFileSync(resolve(HERE, "App.tsx"), "utf8");
    const frozenPages = [
      "pages/fleet/FleetCardsPage.tsx",
      "pages/fleet/FleetEmployeesPage.tsx",
      "pages/fleet/FleetGroupsPage.tsx",
      "pages/fleet/FleetLimitsPage.tsx",
      "pages/fleet/FleetSpendPage.tsx",
      "pages/subscriptions/SubscriptionGamificationPage.tsx",
      "pages/subscriptions/SubscriptionPlanDetailsPage.tsx",
      "pages/subscriptions/SubscriptionPlansPage.tsx",
      "pages/TariffsPage.tsx",
      "pages/partners/PartnerLegalPage.tsx",
    ];

    expect(appSource).not.toContain('path="/fleet');
    expect(appSource).not.toContain('path="/subscriptions');
    expect(appSource).not.toContain('path="/tariffs');

    frozenPages.forEach((relativePath) => {
      const absolutePath = resolve(HERE, relativePath);
      const importPath = `./${relativePath.replace(/\.tsx$/, "")}`;
      expect(existsSync(absolutePath)).toBe(true);
      expect(appSource).not.toContain(importPath);
    });
  });

  it("keeps marketplace helper admin families frozen behind moderation routes", () => {
    const appSource = readFileSync(resolve(HERE, "App.tsx"), "utf8");

    expect(appSource).toContain('path="/marketplace/moderation"');
    expect(appSource).toContain('path="/marketplace/moderation/product/:id"');
    expect(appSource).toContain('path="/marketplace/moderation/service/:id"');
    expect(appSource).toContain('path="/marketplace/moderation/offer/:id"');
    expect(appSource).not.toContain('path="/marketplace/orders');
    expect(appSource).not.toContain('path="/marketplace/orders/:id"');
    expect(appSource).not.toContain('path="/marketplace/orders/:id/sla"');
    expect(appSource).not.toContain('path="/marketplace/orders/:id/consequences"');
    expect(appSource).not.toContain('path="/marketplace/orders/:id/settlement"');
    expect(appSource).not.toContain('path="/marketplace/orders/:id/settlement-snapshot"');
    expect(appSource).not.toContain('path="/marketplace/sponsored');
    expect(appSource).not.toContain('path="/marketplace/contracts');
    expect(appSource).not.toContain('path="/products');
    expect(appSource).not.toContain('path="/contracts"');
  });
});
