import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchInvoiceDetails } from "../api/invoices";
import { useAuth } from "../auth/AuthContext";
import type { ClientInvoiceDetails } from "../types/invoices";
import { formatDate, formatLiters, formatMoney } from "../utils/format";

export function ClientInvoiceDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [invoice, setInvoice] = useState<ClientInvoiceDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    fetchInvoiceDetails(id, user)
      .then(setInvoice)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user]);

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
  }

  if (isLoading || !invoice) {
    return (
      <div className="card">
        <div className="muted">Загружаем счет...</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Счет {invoice.id}</h2>
          <p className="muted">
            Период {formatDate(invoice.period_from)} – {formatDate(invoice.period_to)} | Статус {invoice.status}
          </p>
        </div>
        <button type="button" className="secondary" disabled>
          Скачать PDF
        </button>
      </div>

      <div className="stats-grid">
        <div className="stat">
          <div className="stat__label">Сумма</div>
          <div className="stat__value">{formatMoney(invoice.total_amount, invoice.currency)}</div>
        </div>
        <div className="stat">
          <div className="stat__label">НДС</div>
          <div className="stat__value">{formatMoney(invoice.tax_amount, invoice.currency)}</div>
        </div>
        <div className="stat">
          <div className="stat__label">Итого</div>
          <div className="stat__value">{formatMoney(invoice.total_with_tax, invoice.currency)}</div>
        </div>
      </div>

      <h3>Детализация</h3>
      {invoice.lines.length === 0 ? (
        <p className="muted">Линии счета отсутствуют.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Карта</th>
              <th>Продукт</th>
              <th>Литры</th>
              <th>Сумма</th>
              <th>НДС</th>
            </tr>
          </thead>
          <tbody>
            {invoice.lines.map((line, idx) => (
              <tr key={`${line.card_id}-${line.product_id}-${idx}`}>
                <td>{line.card_id ?? "—"}</td>
                <td>{line.product_id}</td>
                <td>{formatLiters(line.liters)}</td>
                <td>{formatMoney(line.amount, invoice.currency)}</td>
                <td>{formatMoney(line.tax_amount, invoice.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
