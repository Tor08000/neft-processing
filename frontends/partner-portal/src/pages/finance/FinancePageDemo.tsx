import { DemoEmptyState } from "../../components/DemoEmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { formatCurrency, formatDateTime } from "../../utils/format";
import { demoBalance, demoLedgerMovements, demoLedgerTotals } from "../../demo/partnerDemoData";
import type { PartnerLedgerEntry } from "../../types/partnerFinance";

const resolveLedgerSource = (entry: PartnerLedgerEntry) => {
  const meta = entry.meta_json ?? {};
  const sourceType = typeof meta.source_type === "string" ? meta.source_type : null;
  const sourceId = typeof meta.source_id === "string" ? meta.source_id : null;
  if (sourceType === "payout_request") return `Payout ${sourceId ?? "—"}`;
  if (sourceType === "marketplace_order" || sourceType === "partner_order" || sourceType === "order") {
    return `Order ${sourceId ?? entry.order_id ?? "—"}`;
  }
  return sourceId ? `${sourceType ?? "Источник"} ${sourceId}` : "—";
};

export function FinancePageDemo() {
  const currency = demoBalance.currency ?? "RUB";

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Баланс</h2>
        </div>
        <div className="grid three">
          <div className="metric-card">
            <div className="muted">Доступно</div>
            <strong>{formatCurrency(demoBalance.balance_available ?? null, currency)}</strong>
          </div>
          <div className="metric-card">
            <div className="muted">Ожидает</div>
            <strong>{formatCurrency(demoBalance.balance_pending ?? null, currency)}</strong>
          </div>
          <div className="metric-card">
            <div className="muted">Заблокировано</div>
            <strong>{formatCurrency(demoBalance.balance_blocked ?? null, currency)}</strong>
          </div>
        </div>
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Итоги по счёту</h2>
        </div>
        <div className="grid three">
          <div className="metric-card">
            <div className="muted">Поступления</div>
            <strong>{formatCurrency(demoLedgerTotals.in ?? null, currency)}</strong>
          </div>
          <div className="metric-card">
            <div className="muted">Списания</div>
            <strong>{formatCurrency(demoLedgerTotals.out ?? null, currency)}</strong>
          </div>
          <div className="metric-card">
            <div className="muted">Итого</div>
            <strong>{formatCurrency(demoLedgerTotals.net ?? null, currency)}</strong>
          </div>
        </div>
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Движения по счёту</h2>
        </div>
        {demoLedgerMovements.length === 0 ? (
          <DemoEmptyState
            title="Раздел доступен в рабочем контуре"
            description="В демо-режиме показана только часть операций."
          />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Тип</th>
                <th>Сумма</th>
                <th>Направление</th>
                <th>Заказ</th>
                <th>Источник</th>
              </tr>
            </thead>
            <tbody>
              {demoLedgerMovements.map((entry) => (
                <tr key={entry.id}>
                  <td>{formatDateTime(entry.created_at)}</td>
                  <td>
                    <StatusBadge status={entry.entry_type} />
                  </td>
                  <td>{formatCurrency(entry.amount ?? null, entry.currency)}</td>
                  <td>{entry.direction}</td>
                  <td className="mono">{entry.order_id ?? "—"}</td>
                  <td>{resolveLedgerSource(entry)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Экспорт расчётов</h2>
        </div>
        <DemoEmptyState
          title="Экспорт доступен в рабочем контуре"
          description="В демо-режиме экспорт недоступен. В рабочем контуре доступны выгрузки по расчетам."
        />
      </section>
    </div>
  );
}
