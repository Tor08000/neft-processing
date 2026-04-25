import { render, screen } from "@testing-library/react";
import { AuthProvider } from "../auth/AuthContext";
import type { AuthSession } from "../api/types";
import { describe, expect, it, vi } from "vitest";
import { DocumentsPage } from "./documents/DocumentsPage";
import { FinancePage } from "./finance/FinancePage";
import { PayoutsPage } from "./payouts/PayoutsPage";
import { AnalyticsPage } from "./analytics/AnalyticsPage";
import { OrdersPage } from "./orders/OrdersPage";
import { ServicesCatalogPage } from "./services/ServicesCatalogPage";

vi.mock("./documents/DocumentsPageProd", () => ({
  DocumentsPageProd: () => <div>prod-documents</div>,
}));
vi.mock("./finance/FinancePageProd", () => ({
  FinancePageProd: () => <div>prod-finance</div>,
}));
vi.mock("./payouts/PayoutsPageProd", () => ({
  PayoutsPageProd: () => <div>prod-payouts</div>,
}));
vi.mock("./analytics/AnalyticsPageProd", () => ({
  AnalyticsPageProd: () => <div>prod-analytics</div>,
}));
vi.mock("./orders/OrdersPageProd", () => ({
  OrdersPageProd: () => <div>prod-orders</div>,
}));
vi.mock("./services/ServicesCatalogPageProd", () => ({
  ServicesCatalogPageProd: () => <div>prod-services</div>,
}));

const demoSession: AuthSession = {
  token: "token-demo",
  email: "partner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const renderWithSession = (session: AuthSession, node: JSX.Element) =>
  render(<AuthProvider initialSession={session}>{node}</AuthProvider>);

describe("partner wrapper pages", () => {
  it("always render the prod documents page even for demo email", () => {
    renderWithSession(demoSession, <DocumentsPage />);
    expect(screen.getByText("prod-documents")).toBeInTheDocument();
  });

  it("always render the prod finance page even for demo email", () => {
    renderWithSession(demoSession, <FinancePage />);
    expect(screen.getByText("prod-finance")).toBeInTheDocument();
  });

  it("always render the prod payouts page even for demo email", () => {
    renderWithSession(demoSession, <PayoutsPage />);
    expect(screen.getByText("prod-payouts")).toBeInTheDocument();
  });

  it("always render the prod analytics page even for demo email", () => {
    renderWithSession(demoSession, <AnalyticsPage />);
    expect(screen.getByText("prod-analytics")).toBeInTheDocument();
  });

  it("always render the prod orders page even for demo email", () => {
    renderWithSession(demoSession, <OrdersPage />);
    expect(screen.getByText("prod-orders")).toBeInTheDocument();
  });

  it("always render the prod services catalog page even for demo email", () => {
    renderWithSession(demoSession, <ServicesCatalogPage />);
    expect(screen.getByText("prod-services")).toBeInTheDocument();
  });
});
