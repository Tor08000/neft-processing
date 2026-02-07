import { useMemo, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { DemoEmptyState } from "../../components/DemoEmptyState";
import { EmptyState } from "../../components/EmptyState";
import { PriceAnalyticsCharts } from "../../components/PriceAnalyticsCharts";
import { ChartFrame } from "@shared/ui/charts/ChartFrame";
import { useAuth } from "../../auth/AuthContext";
import { useTranslation } from "react-i18next";
import { formatCurrency, formatDate, formatNumber } from "../../utils/format";
import { canReadPriceAnalytics } from "../../utils/roles";
import { demoAnalyticsOffers, demoAnalyticsSeries, demoAnalyticsVersions, demoInsights } from "../../demo/partnerDemoData";
import type { PriceAnalyticsVersion } from "../../types/prices";

const buildDefaultRange = () => {
  const today = new Date();
  const from = new Date();
  from.setDate(today.getDate() - 30);
  return {
    from: from.toISOString().slice(0, 10),
    to: today.toISOString().slice(0, 10),
  };
};

const formatPercent = (value: number | null) => {
  if (value === null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(0)}%`;
};

export function AnalyticsPageDemo() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [filters, setFilters] = useState(buildDefaultRange);
  const [selectedVersion, setSelectedVersion] = useState<string>(demoAnalyticsVersions[0]?.price_version_id ?? "");
  const [compareLeft, setCompareLeft] = useState<string>(demoAnalyticsVersions[0]?.price_version_id ?? "");
  const [compareRight, setCompareRight] = useState<string>(demoAnalyticsVersions[1]?.price_version_id ?? "");
  const [offerSort, setOfferSort] = useState<"orders" | "revenue">("orders");

  const canRead = canReadPriceAnalytics(user?.roles);

  const comparison = useMemo(() => {
    const left = demoAnalyticsVersions.find((version) => version.price_version_id === compareLeft);
    const right = demoAnalyticsVersions.find((version) => version.price_version_id === compareRight);
    if (!left || !right) return null;
    const ordersDelta =
      left.orders_count > 0 ? ((right.orders_count - left.orders_count) / left.orders_count) * 100 : null;
    const revenueDelta =
      left.revenue_total > 0 ? ((right.revenue_total - left.revenue_total) / left.revenue_total) * 100 : null;
    return {
      ordersDelta,
      revenueDelta,
    };
  }, [compareLeft, compareRight]);

  const sortedOffers = useMemo(() => {
    const list = [...demoAnalyticsOffers];
    return list.sort((a, b) => {
      if (offerSort === "orders") {
        return b.orders_count - a.orders_count;
      }
      return b.revenue_total - a.revenue_total;
    });
  }, [offerSort]);

  const isEmpty = !demoAnalyticsVersions.length && !demoAnalyticsOffers.length && !demoInsights.length;

  if (!canRead) {
    return (
      <DemoEmptyState
        title="Раздел доступен в рабочем контуре"
        description="Доступ к аналитике появится после перехода в рабочий контур."
      />
    );
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("priceAnalyticsPage.title")}</h2>
            <p className="muted">{t("priceAnalyticsPage.subtitle")}</p>
          </div>
        </div>
        <div className="tabs">
          <NavLink to="/prices" className={({ isActive }) => `tab ${isActive ? "tab--active" : ""}`}>
            {t("pricesPage.tabs.versions")}
          </NavLink>
          <NavLink to="/prices/analytics" className={({ isActive }) => `tab ${isActive ? "tab--active" : ""}`}>
            {t("pricesPage.tabs.analytics")}
          </NavLink>
        </div>
        <div className="form-grid">
          <label className="form-field">
            <span className="label">{t("priceAnalyticsPage.filters.from")}</span>
            <input
              type="date"
              value={filters.from}
              onChange={(event) => setFilters((prev) => ({ ...prev, from: event.target.value }))}
            />
          </label>
          <label className="form-field">
            <span className="label">{t("priceAnalyticsPage.filters.to")}</span>
            <input
              type="date"
              value={filters.to}
              onChange={(event) => setFilters((prev) => ({ ...prev, to: event.target.value }))}
            />
          </label>
          <label className="form-field">
            <span className="label">{t("priceAnalyticsPage.filters.version")}</span>
            <select value={selectedVersion} onChange={(event) => setSelectedVersion(event.target.value)}>
              <option value="">{t("priceAnalyticsPage.filters.selectVersion")}</option>
              {demoAnalyticsVersions.map((version: PriceAnalyticsVersion) => (
                <option key={version.price_version_id} value={version.price_version_id}>
                  {version.price_version_id}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="notice">
          <div>В демо-режиме отображаются примерные данные аналитики.</div>
        </div>
      </section>

      {isEmpty ? (
        <EmptyState title={t("priceAnalyticsPage.empty.title")} description={t("priceAnalyticsPage.empty.subtitle")} />
      ) : (
        <>
          <section className="card">
            <div className="section-title">
              <div>
                <h3>{t("priceAnalyticsPage.blocks.versions.title")}</h3>
                <p className="muted">{t("priceAnalyticsPage.blocks.versions.subtitle")}</p>
              </div>
            </div>
            <div className="form-grid">
              <label className="form-field">
                <span className="label">{t("priceAnalyticsPage.blocks.versions.compareLeft")}</span>
                <select value={compareLeft} onChange={(event) => setCompareLeft(event.target.value)}>
                  <option value="">{t("priceAnalyticsPage.filters.selectVersion")}</option>
                  {demoAnalyticsVersions.map((version) => (
                    <option key={version.price_version_id} value={version.price_version_id}>
                      {version.price_version_id}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                <span className="label">{t("priceAnalyticsPage.blocks.versions.compareRight")}</span>
                <select value={compareRight} onChange={(event) => setCompareRight(event.target.value)}>
                  <option value="">{t("priceAnalyticsPage.filters.selectVersion")}</option>
                  {demoAnalyticsVersions.map((version) => (
                    <option key={version.price_version_id} value={version.price_version_id}>
                      {version.price_version_id}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("priceAnalyticsPage.blocks.versions.table.version")}</th>
                  <th>{t("priceAnalyticsPage.blocks.versions.table.publishedAt")}</th>
                  <th>{t("priceAnalyticsPage.blocks.versions.table.orders")}</th>
                  <th>{t("priceAnalyticsPage.blocks.versions.table.revenue")}</th>
                  <th>{t("priceAnalyticsPage.blocks.versions.table.avgOrder")}</th>
                  <th>{t("priceAnalyticsPage.blocks.versions.table.refunds")}</th>
                </tr>
              </thead>
              <tbody>
                {demoAnalyticsVersions.map((version) => (
                  <tr key={version.price_version_id}>
                    <td>{version.price_version_id}</td>
                    <td>{formatDate(version.published_at)}</td>
                    <td>{formatNumber(version.orders_count)}</td>
                    <td>{formatCurrency(version.revenue_total)}</td>
                    <td>{formatCurrency(version.avg_order_value)}</td>
                    <td>{formatNumber(version.refunds_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {comparison && (
              <div className="notice">
                <strong>{t("priceAnalyticsPage.blocks.versions.compareTitle")}</strong>
                <div className="muted">
                  {t("priceAnalyticsPage.blocks.versions.compareOrders", { value: formatPercent(comparison.ordersDelta) })}{" "}
                  ·{" "}
                  {t("priceAnalyticsPage.blocks.versions.compareRevenue", {
                    value: formatPercent(comparison.revenueDelta),
                  })}
                </div>
              </div>
            )}
          </section>

          <ChartFrame
            title={t("priceAnalyticsPage.blocks.timeline.title")}
            subtitle={t("priceAnalyticsPage.blocks.timeline.subtitle")}
            isEmpty={!demoAnalyticsSeries.length}
            emptyDescription={t("priceAnalyticsPage.blocks.timeline.empty")}
          >
            <PriceAnalyticsCharts series={demoAnalyticsSeries} />
          </ChartFrame>

          <section className="card">
            <div className="section-title">
              <div>
                <h3>{t("priceAnalyticsPage.blocks.offers.title")}</h3>
                <p className="muted">{t("priceAnalyticsPage.blocks.offers.subtitle")}</p>
              </div>
              <label className="form-field">
                <span className="label">{t("priceAnalyticsPage.blocks.offers.sortLabel")}</span>
                <select value={offerSort} onChange={(event) => setOfferSort(event.target.value as "orders" | "revenue")}>
                  <option value="orders">{t("priceAnalyticsPage.blocks.offers.sortOrders")}</option>
                  <option value="revenue">{t("priceAnalyticsPage.blocks.offers.sortRevenue")}</option>
                </select>
              </label>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("priceAnalyticsPage.blocks.offers.table.offer")}</th>
                  <th>{t("priceAnalyticsPage.blocks.offers.table.price")}</th>
                  <th>{t("priceAnalyticsPage.blocks.offers.table.orders")}</th>
                  <th>{t("priceAnalyticsPage.blocks.offers.table.conversion")}</th>
                  <th>{t("priceAnalyticsPage.blocks.offers.table.revenue")}</th>
                </tr>
              </thead>
              <tbody>
                {sortedOffers.map((offer) => (
                  <tr key={offer.offer_id}>
                    <td>{offer.offer_id}</td>
                    <td>{formatCurrency(offer.avg_price)}</td>
                    <td>{formatNumber(offer.orders_count)}</td>
                    <td>{offer.conversion_rate !== null ? `${(offer.conversion_rate * 100).toFixed(0)}%` : "—"}</td>
                    <td>{formatCurrency(offer.revenue_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <div className="section-title">
              <div>
                <h3>{t("priceAnalyticsPage.blocks.insights.title")}</h3>
                <p className="muted">{t("priceAnalyticsPage.blocks.insights.subtitle")}</p>
              </div>
            </div>
            {demoInsights.length ? (
              <div className="stack">
                {demoInsights.map((insight, index) => (
                  <div key={`${insight.type}-${index}`} className="notice">
                    <div>{insight.message}</div>
                    <div className="muted">
                      {t("priceAnalyticsPage.blocks.insights.period", { from: filters.from, to: filters.to })}
                    </div>
                    {insight.price_version_id ? (
                      <Link to={`/prices/${insight.price_version_id}`} className="ghost">
                        {t("priceAnalyticsPage.blocks.insights.viewVersion")}
                      </Link>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="muted">{t("priceAnalyticsPage.blocks.insights.empty")}</div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
