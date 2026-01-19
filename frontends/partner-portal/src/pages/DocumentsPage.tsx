import { useEffect, useState } from "react";
import { fetchPartnerActs, fetchPartnerInvoices } from "../api/partnerFinance";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { ErrorState, LoadingState } from "../components/states";
import { formatCurrency, formatDate } from "../utils/format";
import type { PartnerDocument } from "../types/partnerFinance";

export function DocumentsPage() {
  const { user } = useAuth();
  const [invoices, setInvoices] = useState<PartnerDocument[]>([]);
  const [acts, setActs] = useState<PartnerDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    Promise.all([fetchPartnerInvoices(user.token), fetchPartnerActs(user.token)])
      .then(([invoiceResp, actResp]) => {
        if (!active) return;
        setInvoices(invoiceResp.items ?? []);
        setActs(actResp.items ?? []);
      })
      .catch((err) => {
        console.error(err);
        if (active) setError("Не удалось загрузить документы");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user]);

  const renderTable = (items: PartnerDocument[], emptyText: string) => {
    if (items.length === 0) {
      return (
        <div className="empty-state">
          <strong>Документы отсутствуют</strong>
          <span className="muted">{emptyText}</span>
        </div>
      );
    }
    return (
      <table className="data-table">
        <thead>
          <tr>
            <th>Период</th>
            <th>Сумма</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          {items.map((doc) => (
            <tr key={doc.id}>
              <td>
                {formatDate(doc.period_from)} — {formatDate(doc.period_to)}
              </td>
              <td>{formatCurrency(doc.total_amount ?? null, doc.currency)}</td>
              <td>
                <StatusBadge status={doc.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Счета</h2>
        </div>
        {isLoading ? <LoadingState /> : error ? <ErrorState description={error} /> : renderTable(invoices, "Новые счета появятся в конце месяца.")}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Акты</h2>
        </div>
        {isLoading ? <LoadingState /> : error ? <ErrorState description={error} /> : renderTable(acts, "Акты появятся после начислений.")}
      </section>
    </div>
  );
}
