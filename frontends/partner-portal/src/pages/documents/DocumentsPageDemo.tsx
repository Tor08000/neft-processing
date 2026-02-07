import { DemoEmptyState } from "../../components/DemoEmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { formatCurrency, formatDate } from "../../utils/format";
import { demoActs, demoInvoices } from "../../demo/partnerDemoData";

type DemoDocument = {
  id: string;
  number: string;
  date: string;
  amount: number;
  status: string;
};

const renderDemoTable = (items: DemoDocument[]) => {
  if (items.length === 0) {
    return (
      <DemoEmptyState
        title="Раздел доступен в рабочем контуре"
        description="В демо-режиме показан ограниченный набор данных."
      />
    );
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Документ</th>
          <th>Дата</th>
          <th>Сумма</th>
          <th>Статус</th>
          <th>Скачать</th>
        </tr>
      </thead>
      <tbody>
        {items.map((doc) => (
          <tr key={doc.id}>
            <td>{doc.number}</td>
            <td>{formatDate(doc.date)}</td>
            <td>{formatCurrency(doc.amount, "RUB")}</td>
            <td>
              <StatusBadge status={doc.status} />
            </td>
            <td>
              <button type="button" className="secondary" disabled>
                Скачать
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

export function DocumentsPageDemo() {
  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Счета</h2>
        </div>
        {renderDemoTable(demoInvoices)}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Акты</h2>
        </div>
        {renderDemoTable(demoActs)}
      </section>
    </div>
  );
}
