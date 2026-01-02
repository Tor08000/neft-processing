import React, { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { listInvoices, listPayments, listRefunds, listReconciliationLinks } from "../../api/billing";

const buildDateRange = () => {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 30);
  return { start, end };
};

const toIsoDate = (date: Date) => date.toISOString();

const SummaryCard: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
  <div className="explain-summary__card">
    <div className="explain-summary__label">{label}</div>
    <div className="explain-summary__value">{value}</div>
  </div>
);

const BillingOverviewPage: React.FC = () => {
  const location = useLocation();
  const [summary, setSummary] = useState<{
    invoices: string;
    payments: string;
    refunds: string;
    links: string;
    mismatched: string;
  }>({
    invoices: "—",
    payments: "—",
    refunds: "—",
    links: "—",
    mismatched: "—",
  });

  const tabs = useMemo(
    () => [
      { label: "Invoices", path: "/billing/invoices" },
      { label: "Payments", path: "/billing/payments" },
      { label: "Refunds", path: "/billing/refunds" },
      { label: "Links", path: "/billing/links" },
    ],
    [],
  );

  useEffect(() => {
    let isMounted = true;
    const { start, end } = buildDateRange();
    const dateFrom = toIsoDate(start);
    const dateTo = toIsoDate(end);

    Promise.all([
      listInvoices({ limit: 1, offset: 0, date_from: dateFrom, date_to: dateTo }),
      listPayments({ limit: 1, offset: 0, date_from: dateFrom, date_to: dateTo }),
      listRefunds({ limit: 1, offset: 0, date_from: dateFrom, date_to: dateTo }),
      listReconciliationLinks({ limit: 1, offset: 0, status: "PENDING", date_from: dateFrom, date_to: dateTo }),
      listReconciliationLinks({ limit: 1, offset: 0, status: "MISMATCHED", date_from: dateFrom, date_to: dateTo }),
    ])
      .then(([invoices, payments, refunds, pendingLinks, mismatchedLinks]) => {
        if (!isMounted) return;
        setSummary({
          invoices: invoices.unavailable ? "—" : String(invoices.total),
          payments: payments.unavailable ? "—" : String(payments.total),
          refunds: refunds.unavailable ? "—" : String(refunds.total),
          links: pendingLinks.unavailable ? "—" : String(pendingLinks.total),
          mismatched: mismatchedLinks.unavailable ? "—" : String(mismatchedLinks.total),
        });
      })
      .catch(() => {
        if (!isMounted) return;
        setSummary({ invoices: "—", payments: "—", refunds: "—", links: "—", mismatched: "—" });
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>Billing</h1>
            <p className="muted">Invoices, payments, refunds, and reconciliation links overview.</p>
          </div>
          <div className="muted">Last 30 days</div>
        </div>
        <div className="explain-summary">
          <SummaryCard label="Invoices issued" value={summary.invoices} />
          <SummaryCard label="Payments captured" value={summary.payments} />
          <SummaryCard label="Refunds" value={summary.refunds} />
          <SummaryCard label="Links pending" value={summary.links} />
          <SummaryCard label="Links mismatched" value={summary.mismatched} />
        </div>
      </section>

      <div className="card" style={{ padding: 12 }}>
        <div className="pill-list">
          {tabs.map((tab) => {
            const isActive = location.pathname === tab.path || location.pathname.startsWith(`${tab.path}/`);
            return (
              <Link
                key={tab.path}
                to={tab.path}
                className={`pill pill--outline${isActive ? " pill--accent" : ""}`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </div>

      <Outlet />
    </div>
  );
};

export default BillingOverviewPage;
