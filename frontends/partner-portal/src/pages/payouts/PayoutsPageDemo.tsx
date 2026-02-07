import { DemoEmptyState } from "../../components/DemoEmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { formatCurrency, formatDateTime } from "../../utils/format";
import { demoPayoutHistory, demoPayoutStatus, payoutRequestDisabledReason } from "../../demo/partnerDemoData";

export function PayoutsPageDemo() {
  const currency = demoPayoutStatus.currency ?? "RUB";

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Запросить выплату</h2>
        </div>
        <div className="notice">
          <div>{payoutRequestDisabledReason}</div>
        </div>
        <div className="form-grid">
          <label className="field">
            <span className="label">Сумма</span>
            <input type="number" min={0} value={demoPayoutStatus.availableAmount} disabled />
          </label>
          <label className="field">
            <span className="label">Валюта</span>
            <input type="text" value={currency} disabled />
          </label>
          <div className="field">
            <button className="primary" type="button" disabled title={payoutRequestDisabledReason}>
              Запросить
            </button>
          </div>
        </div>
      </section>
      <section className="card">
        <div className="section-title">
          <h2>История выплат</h2>
        </div>
        {demoPayoutHistory.length === 0 ? (
          <DemoEmptyState
            title="Раздел доступен в рабочем контуре"
            description="В демо-режиме история выплат ограничена."
          />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Причина</th>
              </tr>
            </thead>
            <tbody>
              {demoPayoutHistory.map((item) => (
                <tr key={item.id}>
                  <td>{formatDateTime(item.created_at)}</td>
                  <td>{formatCurrency(item.amount ?? null, item.currency)}</td>
                  <td>
                    <StatusBadge status={item.status} />
                  </td>
                  <td>{item.blocked_reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
