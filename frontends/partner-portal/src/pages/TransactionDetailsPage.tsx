import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchTransactionDetail, type TransactionDetail } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatDateTime, formatNumber } from "../utils/format";

export function TransactionDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [transaction, setTransaction] = useState<TransactionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user || !id) return;
    setIsLoading(true);
    fetchTransactionDetail(user.token, id)
      .then((data) => {
        if (active) {
          setTransaction(data);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить операцию");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [user, id]);

  if (isLoading) {
    return (
      <div className="card">
        <div className="skeleton-stack" aria-busy="true">
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  if (!transaction) {
    return (
      <div className="empty-state empty-state--full">
        <h2>Операция не найдена</h2>
        <Link className="ghost" to="/transactions">
          Вернуться к списку
        </Link>
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Операция {transaction.id}</h2>
          <Link className="ghost" to="/transactions">
            Назад
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Время</div>
            <div>{formatDateTime(transaction.ts)}</div>
          </div>
          <div>
            <div className="label">Станция</div>
            <div>{transaction.station}</div>
          </div>
          <div>
            <div className="label">Продукт</div>
            <div>{transaction.product}</div>
          </div>
          <div>
            <div className="label">Кол-во</div>
            <div>{formatNumber(transaction.quantity ?? null)}</div>
          </div>
          <div>
            <div className="label">Сумма</div>
            <div>{formatCurrency(transaction.amount)}</div>
          </div>
          <div>
            <div className="label">Статус</div>
            <StatusBadge status={transaction.status} />
          </div>
          <div>
            <div className="label">Терминал</div>
            <div>{transaction.terminalId ?? "—"}</div>
          </div>
          <div>
            <div className="label">Карта</div>
            <div>{transaction.cardMasked ?? "—"}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Связанные ссылки</h3>
        <div className="actions">
          {transaction.moneyFlowUrl ? (
            <a className="link-button" href={transaction.moneyFlowUrl} target="_blank" rel="noreferrer">
              Money-flow summary
            </a>
          ) : (
            <span className="muted">Money-flow недоступен</span>
          )}
          {transaction.explainUrl ? (
            <a className="link-button" href={transaction.explainUrl} target="_blank" rel="noreferrer">
              Explain
            </a>
          ) : (
            <span className="muted">Explain недоступен</span>
          )}
        </div>
      </section>
    </div>
  );
}
