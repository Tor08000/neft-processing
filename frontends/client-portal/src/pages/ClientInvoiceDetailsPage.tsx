import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchClientInvoiceDetails } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import type { ClientInvoiceDetails } from "../types/portal";
import { MoneyValue } from "../components/common/MoneyValue";
import { AppErrorState, AppLoadingState } from "../components/states";
import { formatDate, formatDateTime, formatNumberParts } from "../utils/format";
import { getInvoiceStatusLabel, getInvoiceStatusTone } from "../utils/invoices";

export function ClientInvoiceDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [invoice, setInvoice] = useState<ClientInvoiceDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    fetchClientInvoiceDetails(user, id)
      .then((data) => setInvoice(data))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user]);

  if (!id) {
    return null;
  }

  if (isLoading) {
    return <AppLoadingState />;
  }

  if (error) {
    return <AppErrorState message={error} />;
  }

  if (!invoice) {
    return <AppErrorState message="Инвойс не найден" />;
  }

  const usageLines = invoice.lines?.filter((line) => line.line_type === "USAGE") ?? [];
  const formatQuantity = (value?: number | null) => {
    if (value === null || value === undefined) return "—";
    const parts = formatNumberParts(value, 2);
    return parts.fraction ? `${parts.int}.${parts.fraction}` : parts.int;
  };

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>{invoice.invoice_number}</h2>
            <p className="muted">Инвойс за период {formatDate(invoice.period_start)} — {formatDate(invoice.period_end)}</p>
          </div>
          <div className="actions">
            <Link className="ghost" to="/invoices">
              Назад к списку
            </Link>
            {invoice.download_url ? (
              <a className="ghost" href={invoice.download_url} rel="noreferrer" target="_blank">
                Скачать PDF
              </a>
            ) : null}
          </div>
        </div>
        <div className="stats-grid">
          <div className="stat">
            <span className="muted">Статус</span>
            <strong className={`neft-chip neft-chip-${getInvoiceStatusTone(invoice.status)}`}>
              {getInvoiceStatusLabel(invoice.status)}
            </strong>
          </div>
          <div className="stat">
            <span className="muted">Сумма</span>
            <strong>
              <MoneyValue amount={invoice.amount_total} currency={invoice.currency} />
            </strong>
          </div>
          <div className="stat">
            <span className="muted">Оплачено</span>
            <strong>
              <MoneyValue amount={invoice.amount_paid} currency={invoice.currency} />
            </strong>
          </div>
          <div className="stat">
            <span className="muted">Остаток</span>
            <strong>
              <MoneyValue amount={invoice.amount_due} currency={invoice.currency} />
            </strong>
          </div>
          <div className="stat">
            <span className="muted">Срок оплаты</span>
            <strong>{invoice.due_date ? formatDate(invoice.due_date) : "—"}</strong>
          </div>
        </div>
      </div>

      <section className="card">
        <div className="card__header">
          <h3>Платежи</h3>
        </div>
        {invoice.payments.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Провайдер</th>
                <th>Ссылка</th>
              </tr>
            </thead>
            <tbody>
              {invoice.payments.map((payment) => (
                <tr key={`${payment.external_ref}-${payment.created_at}`}>
                  <td>{formatDateTime(payment.created_at)}</td>
                  <td>
                    <MoneyValue amount={payment.amount} currency={invoice.currency} />
                  </td>
                  <td>{payment.status}</td>
                  <td>{payment.provider ?? "—"}</td>
                  <td>{payment.external_ref ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Платежей пока нет.</p>
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <h3>Начисления за использование</h3>
        </div>
        {usageLines.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Описание</th>
                <th>Количество</th>
                <th>Цена за единицу</th>
                <th>Сумма</th>
              </tr>
            </thead>
            <tbody>
              {usageLines.map((line, index) => (
                <tr key={`${line.ref_code ?? "usage"}-${index}`}>
                  <td>{line.description ?? line.ref_code ?? "Usage"}</td>
                  <td>{formatQuantity(line.quantity ?? undefined)}</td>
                  <td>
                    {line.unit_price !== null && line.unit_price !== undefined ? (
                      <MoneyValue amount={line.unit_price} currency={invoice.currency} />
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {line.amount !== null && line.amount !== undefined ? (
                      <MoneyValue amount={line.amount} currency={invoice.currency} />
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Начислений за использование пока нет.</p>
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <h3>Возвраты</h3>
        </div>
        {invoice.refunds.length ? (
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
              {invoice.refunds.map((refund) => (
                <tr key={`${refund.external_ref}-${refund.created_at}`}>
                  <td>{formatDateTime(refund.created_at)}</td>
                  <td>
                    <MoneyValue amount={refund.amount} currency={invoice.currency} />
                  </td>
                  <td>{refund.status}</td>
                  <td>{refund.reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Возвратов пока нет.</p>
        )}
      </section>
    </div>
  );
}
