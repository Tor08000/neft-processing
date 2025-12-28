import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import TariffsPage from "./TariffsPage";
import InvoicesListPage from "./InvoicesListPage";
import InvoiceDetailsPage from "./InvoiceDetailsPage";
import * as billingApi from "../api/billing";

const Wrapper: React.FC<React.PropsWithChildren> = ({ children }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe("Admin billing UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders tariff list and prices", async () => {
    vi.spyOn(billingApi, "fetchTariffs").mockResolvedValue({ items: [{ id: "t1", name: "Base" }], total: 1, limit: 50, offset: 0 });
    vi.spyOn(billingApi, "fetchTariffPrices").mockResolvedValue({ items: [{ id: 1, tariff_id: "t1", product_id: "prod", price_per_liter: "10", currency: "RUB", priority: 1 }] });
    vi.spyOn(billingApi, "upsertTariffPrice").mockResolvedValue({ id: 2, tariff_id: "t1", product_id: "prod", price_per_liter: "11", currency: "RUB", priority: 1 });

    const user = userEvent.setup();

    render(
      <Wrapper>
        <TariffsPage />
      </Wrapper>,
    );

    expect(await screen.findByText("Base")).toBeInTheDocument();
    await user.click(screen.getByText("Base"));
    expect(await screen.findByText(/Prices for/)).toBeInTheDocument();
    expect(await screen.findByText("10")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Product/), { target: { value: "prod" } });
    fireEvent.change(screen.getByLabelText(/Price per liter/), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText(/Currency/), { target: { value: "RUB" } });
    fireEvent.submit(screen.getByText("Save price"));

    await waitFor(() => expect(billingApi.upsertTariffPrice).toHaveBeenCalled());
  });

  it("shows invoices list and allows generation", async () => {
    vi.spyOn(billingApi, "fetchInvoices").mockResolvedValue({ items: [{ id: "inv1", client_id: "c1", period_from: "2024-01-01", period_to: "2024-01-31", total_amount: 1000, total_with_tax: 1000, tax_amount: 0, status: "DRAFT" }], total: 1, limit: 50, offset: 0 });
    vi.spyOn(billingApi, "generateInvoices").mockResolvedValue({ created_ids: ["inv2"] });

    const user = userEvent.setup();

    render(
      <Wrapper>
        <MemoryRouter>
          <InvoicesListPage />
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText(/Invoices/)).toBeInTheDocument();
    expect(screen.getByText(/c1/)).toBeInTheDocument();
    await user.click(screen.getByText(/Generate invoices/));
    await waitFor(() => expect(billingApi.generateInvoices).toHaveBeenCalled());
  });

  it("renders invoice details and changes status", async () => {
    vi.spyOn(billingApi, "fetchInvoice").mockResolvedValue({
      id: "inv1",
      client_id: "c1",
      period_from: "2024-01-01",
      period_to: "2024-01-31",
      total_amount: 1000,
      total_with_tax: 1000,
      tax_amount: 0,
      status: "DRAFT",
      lines: [
        {
          id: "line1",
          invoice_id: "inv1",
          product_id: "prod",
          line_amount: 1000,
          tax_amount: 0,
        },
      ],
    });
    vi.spyOn(billingApi, "updateInvoiceStatus").mockResolvedValue({
      id: "inv1",
      client_id: "c1",
      period_from: "2024-01-01",
      period_to: "2024-01-31",
      total_amount: 1000,
      total_with_tax: 1000,
      tax_amount: 0,
      status: "ISSUED",
      lines: [],
    });

    render(
      <Wrapper>
        <MemoryRouter initialEntries={["/billing/invoices/inv1"]}>
          <Routes>
            <Route path="/billing/invoices/:id" element={<InvoiceDetailsPage />} />
          </Routes>
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText(/Invoice inv1/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "ISSUED" } });
    await waitFor(() => expect(billingApi.updateInvoiceStatus).toHaveBeenCalled());
  });
});
