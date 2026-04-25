import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchOverdueList, fetchRevenueSummary, OverdueBucket } from "../../api/revenue";
import { SummaryCard } from "../../components/SummaryCard/SummaryCard";
import { Table, type Column } from "../../components/Table/Table";
import { Loader } from "../../components/Loader/Loader";
import { useAuth } from "../../auth/AuthContext";
import { formatDate, getIsoDate } from "../../utils/format";
import type {
  RevenueAddonMixItem,
  RevenueOverdueBucket,
  RevenueOverdueItem,
  RevenuePlanMixItem,
} from "../../types/revenue";
import { revenuePageCopy } from "../operatorKeyPageCopy";

const formatMoney = (amount: number | null | undefined, currency = "RUB") => {
  if (amount === null || amount === undefined) return "—";
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency,
      currencyDisplay: "symbol",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
};

const bucketLabels: Record<OverdueBucket, string> = {
  all: revenuePageCopy.bucketLabels.all,
  "0_7": revenuePageCopy.bucketLabels["0_7"],
  "8_30": revenuePageCopy.bucketLabels["8_30"],
  "31_90": revenuePageCopy.bucketLabels["31_90"],
  "90_plus": revenuePageCopy.bucketLabels["90_plus"],
};

const downloadCsv = (filename: string, headers: string[], rows: string[][]) => {
  const content = [headers, ...rows].map((row) => row.map((value) => `"${value.replace(/"/g, '""')}"`).join(","));
  const blob = new Blob([content.join("\n")], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
};

export const RevenuePage: React.FC = () => {
  const { accessToken } = useAuth();
  const [asOf, setAsOf] = useState(getIsoDate(new Date()));
  const [bucket, setBucket] = useState<OverdueBucket>("all");
  const [exportingOverdue, setExportingOverdue] = useState(false);

  const summaryQuery = useQuery({
    queryKey: ["revenue-summary", asOf],
    queryFn: () => fetchRevenueSummary(asOf, accessToken),
    enabled: Boolean(accessToken),
    staleTime: 30_000,
  });

  const overdueQuery = useQuery({
    queryKey: ["revenue-overdue", asOf, bucket],
    queryFn: () =>
      fetchOverdueList(
        {
          asOf,
          bucket,
          limit: 20,
          offset: 0,
        },
        accessToken,
      ),
    enabled: Boolean(accessToken),
    staleTime: 30_000,
  });

  const summary = summaryQuery.data;
  const overdue = overdueQuery.data?.items ?? [];
  const currency = summary?.mrr.currency ?? "RUB";

  const knownPlanMix = useMemo(() => (summary?.plan_mix ?? []).filter((row) => row.mrr !== null), [summary]);
  const unknownPlanMix = useMemo(() => (summary?.plan_mix ?? []).filter((row) => row.mrr === null), [summary]);
  const unknownPlanOrgs = unknownPlanMix.reduce((acc, row) => acc + row.orgs, 0);
  const knownOrgCount = knownPlanMix.reduce((acc, row) => acc + row.orgs, 0);
  const customLabel = useMemo(() => {
    if (!unknownPlanMix.length) return null;
    const planSet = new Set(unknownPlanMix.map((row) => row.plan));
    if (planSet.size === 1 && planSet.has("ENTERPRISE")) {
      return "Enterprise custom (MRR unknown)";
    }
    return "Custom pricing (MRR unknown)";
  }, [unknownPlanMix]);

  const planMixDisplay: RevenuePlanMixItem[] = useMemo(() => {
    if (!summary) return [];
    const items = [...knownPlanMix];
    if (customLabel && unknownPlanOrgs > 0) {
      items.push({ plan: customLabel, orgs: unknownPlanOrgs, mrr: null });
    }
    return items;
  }, [customLabel, knownPlanMix, summary, unknownPlanOrgs]);

  const overdueBuckets: RevenueOverdueBucket[] = useMemo(() => summary?.overdue_buckets ?? [], [summary]);

  const planMixColumns: Column<RevenuePlanMixItem>[] = useMemo(
    () => [
      { key: "plan", title: revenuePageCopy.tableTitles.plan, render: (row) => row.plan },
      { key: "orgs", title: revenuePageCopy.tableTitles.orgs, render: (row) => row.orgs },
      {
        key: "mrr",
        title: "MRR",
        render: (row) => formatMoney(row.mrr, currency),
      },
    ],
    [currency],
  );

  const addonMixColumns: Column<RevenueAddonMixItem>[] = useMemo(
    () => [
      { key: "addon", title: "Add-on", render: (row) => row.addon },
      { key: "orgs", title: revenuePageCopy.tableTitles.orgs, render: (row) => row.orgs },
      { key: "mrr", title: "MRR", render: (row) => formatMoney(row.mrr, currency) },
    ],
    [currency],
  );

  const overdueColumns: Column<RevenueOverdueItem>[] = useMemo(
    () => [
      {
        key: "org",
        title: revenuePageCopy.tableTitles.organization,
        render: (row) => row.org_name ?? `#${row.org_id}`,
      },
      {
        key: "invoice",
        title: "Invoice",
        render: (row) => row.invoice_id,
      },
      {
        key: "due_at",
        title: "Due",
        render: (row) => formatDate(row.due_at),
      },
      {
        key: "overdue_days",
        title: revenuePageCopy.tableTitles.overdueDays,
        render: (row) => row.overdue_days,
      },
      {
        key: "amount",
        title: revenuePageCopy.tableTitles.amount,
        render: (row) => formatMoney(row.amount, row.currency ?? currency),
      },
      {
        key: "plan",
        title: revenuePageCopy.tableTitles.planStatus,
        render: (row) => `${row.subscription_plan ?? "—"} / ${row.subscription_status ?? "—"}`,
      },
    ],
    [currency],
  );

  const planMax = Math.max(0, ...planMixDisplay.map((row) => row.mrr ?? 0));
  const addonMax = Math.max(0, ...(summary?.addon_mix ?? []).map((row) => row.mrr ?? 0));

  const renderBar = (value: number | null, max: number) => {
    if (!value || max <= 0) return <div style={{ height: 6, background: "#f1f5f9", borderRadius: 4 }} />;
    const width = Math.max(6, Math.round((value / max) * 100));
    return (
      <div style={{ height: 6, background: "#f1f5f9", borderRadius: 4 }}>
        <div style={{ width: `${width}%`, height: 6, borderRadius: 4, background: "#6366f1" }} />
      </div>
    );
  };

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Revenue</h1>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <label className="filter" style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="label">As of</span>
            <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
          </label>
          {(summaryQuery.isFetching || overdueQuery.isFetching) && <Loader label="Loading revenue" />}
        </div>
      </div>

      {summaryQuery.error ? <div className="card error-state">{revenuePageCopy.states.loadError}</div> : null}
      {summaryQuery.isLoading && !summary ? <div className="card">{revenuePageCopy.states.loading}</div> : null}

      {summary ? (
        <>
          <div className="card-grid" style={{ marginBottom: 16 }}>
            <SummaryCard
              title="MRR (known)"
              value={formatMoney(summary.mrr.amount, summary.mrr.currency)}
              description={`Priced orgs: ${knownOrgCount}`}
            />
            <SummaryCard title="ARR" value={formatMoney(summary.arr.amount, summary.arr.currency)} />
            <SummaryCard title="Active orgs" value={summary.active_orgs} />
            <SummaryCard title="Custom pricing orgs" value={unknownPlanOrgs} />
            <SummaryCard title="Overdue amount" value={formatMoney(summary.overdue_amount, currency)} />
            <SummaryCard title="Overdue orgs" value={summary.overdue_orgs} />
            <SummaryCard title="Usage revenue MTD" value={formatMoney(summary.usage_revenue_mtd, currency)} />
          </div>

          <div className="card-grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <section className="card">
              <div className="card__header">
                <h3>Plan mix</h3>
              </div>
              <div className="stack">
                {planMixDisplay.map((row) => (
                  <div key={row.plan} style={{ display: "grid", gridTemplateColumns: "120px 1fr 160px", gap: 12 }}>
                    <div>{row.plan}</div>
                    {renderBar(row.mrr, planMax)}
                    <div style={{ textAlign: "right" }}>{formatMoney(row.mrr, currency)}</div>
                  </div>
                ))}
                {!planMixDisplay.length ? <div className="muted">{revenuePageCopy.states.noData}</div> : null}
              </div>
            </section>

            <section className="card">
              <div className="card__header">
                <h3>Add-on mix</h3>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    const rows = (summary.addon_mix ?? []).map((row) => [
                      row.addon,
                      String(row.orgs),
                      formatMoney(row.mrr, currency),
                    ]);
                    downloadCsv(`addon-mix-${asOf}.csv`, ["addon", "orgs", "mrr"], rows);
                  }}
                >
                  Export CSV
                </button>
              </div>
              <div className="stack">
                {(summary.addon_mix ?? []).map((row) => (
                  <div key={row.addon} style={{ display: "grid", gridTemplateColumns: "180px 1fr 160px", gap: 12 }}>
                    <div>{row.addon}</div>
                    {renderBar(row.mrr, addonMax)}
                    <div style={{ textAlign: "right" }}>{formatMoney(row.mrr, currency)}</div>
                  </div>
                ))}
                {!summary.addon_mix?.length ? <div className="muted">{revenuePageCopy.states.noData}</div> : null}
              </div>
            </section>
          </div>

          <section className="card" style={{ marginTop: 16 }}>
            <div className="card__header">
              <h3>Overdue aging</h3>
            </div>
            <div className="card-grid" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12 }}>
              {overdueBuckets.map((row) => (
                <button
                  key={row.bucket}
                  type="button"
                  className={`card neft-card ${bucket === row.bucket ? "is-active" : ""}`}
                  onClick={() => setBucket(row.bucket as OverdueBucket)}
                  style={{ textAlign: "left" }}
                >
                  <div style={{ fontSize: 13, color: "var(--neft-text-muted)" }}>{row.label}</div>
                  <div style={{ fontSize: 22, fontWeight: 700 }}>{formatMoney(row.amount, currency)}</div>
                  <div style={{ fontSize: 12, color: "var(--neft-text-muted)" }}>{row.orgs} orgs</div>
                </button>
              ))}
            </div>
          </section>

          <section className="card" style={{ marginTop: 16 }}>
            <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
              <h3>Overdue (top 20)</h3>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div className="pill-list">
                  {(Object.keys(bucketLabels) as OverdueBucket[]).map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={`pill ${bucket === item ? "pill--active" : ""}`}
                      onClick={() => setBucket(item)}
                    >
                      {bucketLabels[item]}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="ghost"
                  disabled={exportingOverdue}
                  onClick={async () => {
                    if (!accessToken) return;
                    setExportingOverdue(true);
                    try {
                      const pageSize = 100;
                      let offset = 0;
                      let total = 0;
                      const rows: RevenueOverdueItem[] = [];
                      do {
                        const response = await fetchOverdueList(
                          { asOf, bucket, limit: pageSize, offset },
                          accessToken,
                        );
                        rows.push(...response.items);
                        total = response.total;
                        offset += pageSize;
                      } while (offset < total);
                      const csvRows = rows.map((row) => [
                        row.org_name ?? String(row.org_id),
                        row.invoice_id,
                        formatDate(row.due_at),
                        String(row.overdue_days),
                        formatMoney(row.amount, row.currency ?? currency),
                        row.subscription_plan ?? "",
                        row.subscription_status ?? "",
                      ]);
                      downloadCsv(
                        `overdue-${bucket}-${asOf}.csv`,
                        ["org", "invoice_id", "due_at", "overdue_days", "amount", "plan", "status"],
                        csvRows,
                      );
                    } finally {
                      setExportingOverdue(false);
                    }
                  }}
                >
                  {exportingOverdue ? "Exporting..." : "Export CSV"}
                </button>
              </div>
            </div>
            <Table
              columns={overdueColumns}
              data={overdue}
              loading={overdueQuery.isLoading}
              emptyMessage={revenuePageCopy.states.noOverdues}
            />
          </section>

          <div className="card" style={{ marginTop: 16 }}>
            <div className="card__header">
              <h3>Mix details</h3>
            </div>
            <div className="card-grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <Table columns={planMixColumns} data={planMixDisplay} emptyMessage={revenuePageCopy.states.noPlans} />
              <Table columns={addonMixColumns} data={summary.addon_mix ?? []} emptyMessage={revenuePageCopy.states.noAddons} />
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};

export default RevenuePage;
