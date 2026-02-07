import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import type { AuthSession } from "../api/types";
import { DocumentsPage } from "./documents/DocumentsPage";
import { FinancePage } from "./finance/FinancePage";
import { PayoutsPage } from "./payouts/PayoutsPage";
import { AnalyticsPage } from "./analytics/AnalyticsPage";

vi.mock("./documents/DocumentsPageDemo", () => ({
  DocumentsPageDemo: () => <div>demo-documents</div>,
}));
vi.mock("./documents/DocumentsPageProd", () => ({
  DocumentsPageProd: () => <div>prod-documents</div>,
}));
vi.mock("./finance/FinancePageDemo", () => ({
  FinancePageDemo: () => <div>demo-finance</div>,
}));
vi.mock("./finance/FinancePageProd", () => ({
  FinancePageProd: () => <div>prod-finance</div>,
}));
vi.mock("./payouts/PayoutsPageDemo", () => ({
  PayoutsPageDemo: () => <div>demo-payouts</div>,
}));
vi.mock("./payouts/PayoutsPageProd", () => ({
  PayoutsPageProd: () => <div>prod-payouts</div>,
}));
vi.mock("./analytics/AnalyticsPageDemo", () => ({
  AnalyticsPageDemo: () => <div>demo-analytics</div>,
}));
vi.mock("./analytics/AnalyticsPageProd", () => ({
  AnalyticsPageProd: () => <div>prod-analytics</div>,
}));

const demoSession: AuthSession = {
  token: "token-demo",
  email: "partner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const prodSession: AuthSession = {
  token: "token-prod",
  email: "owner@neft.local",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const renderWithSession = (ui: ReactElement, session: AuthSession) =>
  render(<AuthProvider initialSession={session}>{ui}</AuthProvider>);

describe("partner demo routing", () => {
  it("renders demo documents page for demo email", () => {
    renderWithSession(<DocumentsPage />, demoSession);
    expect(screen.getByText("demo-documents")).toBeInTheDocument();
  });

  it("renders prod documents page for non-demo email", () => {
    renderWithSession(<DocumentsPage />, prodSession);
    expect(screen.getByText("prod-documents")).toBeInTheDocument();
  });

  it("renders demo finance page for demo email", () => {
    renderWithSession(<FinancePage />, demoSession);
    expect(screen.getByText("demo-finance")).toBeInTheDocument();
  });

  it("renders prod finance page for non-demo email", () => {
    renderWithSession(<FinancePage />, prodSession);
    expect(screen.getByText("prod-finance")).toBeInTheDocument();
  });

  it("renders demo payouts page for demo email", () => {
    renderWithSession(<PayoutsPage />, demoSession);
    expect(screen.getByText("demo-payouts")).toBeInTheDocument();
  });

  it("renders prod payouts page for non-demo email", () => {
    renderWithSession(<PayoutsPage />, prodSession);
    expect(screen.getByText("prod-payouts")).toBeInTheDocument();
  });

  it("renders demo analytics page for demo email", () => {
    renderWithSession(<AnalyticsPage />, demoSession);
    expect(screen.getByText("demo-analytics")).toBeInTheDocument();
  });

  it("renders prod analytics page for non-demo email", () => {
    renderWithSession(<AnalyticsPage />, prodSession);
    expect(screen.getByText("prod-analytics")).toBeInTheDocument();
  });
});
