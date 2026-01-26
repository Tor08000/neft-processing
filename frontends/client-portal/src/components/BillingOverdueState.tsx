import { Link } from "react-router-dom";
import type { PortalMeResponse } from "../api/clientPortal";
import { MoneyValue } from "./common/MoneyValue";
import { formatDate } from "../utils/format";

type BillingOverdueStateProps = {
  billing?: PortalMeResponse["billing"] | null;
};

export const BillingOverdueState = ({ billing }: BillingOverdueStateProps) => {
  const invoices = billing?.overdue_invoices ?? [];

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Есть просроченный счёт</h2>
            <p className="muted">
              Доступ временно ограничен, пока не подтвердим оплату. Отправьте подтверждение оплаты или свяжитесь с
              поддержкой.
            </p>
          </div>
          <Link className="ghost neft-btn-secondary" to="/client/support/new?topic=billing">
            Связаться с поддержкой
          </Link>
        </div>
        {invoices.length ? (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Счёт</th>
                  <th>Сумма</th>
                  <th>Срок оплаты</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((invoice) => {
                  const currency = invoice.currency ?? "RUB";
                  return (
                    <tr key={invoice.id}>
                      <td>№{invoice.number ?? invoice.id}</td>
                      <td>
                        <MoneyValue amount={Number(invoice.amount ?? 0)} currency={currency} />
                      </td>
                      <td>{invoice.due_at ? formatDate(invoice.due_at) : "—"}</td>
                      <td>
                        <div className="actions">
                          <Link className="neft-btn-primary" to={`/invoices/${invoice.id}`}>
                            Сообщить об оплате
                          </Link>
                          {invoice.download_url ? (
                            <a className="neft-btn-secondary" href={invoice.download_url} rel="noreferrer" target="_blank">
                              Скачать счёт
                            </a>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="muted">Подробности по счёту скоро будут доступны.</div>
        )}
      </div>
    </div>
  );
};
