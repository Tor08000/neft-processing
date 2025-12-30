import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  confirmSettlementReceived,
  fetchSettlementDetail,
  requestReconciliation,
  type SettlementDetail,
} from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { SupportRequestModal } from "../components/SupportRequestModal";
import { formatCurrency, formatDate, formatNumber } from "../utils/format";
import { canManagePayouts } from "../utils/roles";

export function SettlementDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [settlement, setSettlement] = useState<SettlementDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [isSupportOpen, setIsSupportOpen] = useState(false);

  useEffect(() => {
    let active = true;
    if (!user || !id) return;
    setIsLoading(true);
    fetchSettlementDetail(user.token, id)
      .then((data) => {
        if (active) {
          setSettlement(data);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить settlement");
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

  const handleConfirm = async () => {
    if (!user || !id) return;
    setIsActionLoading(true);
    setActionMessage(null);
    try {
      await confirmSettlementReceived(user.token, id);
      setActionMessage("Подтверждение отправлено");
    } catch (err) {
      console.error(err);
      setActionMessage("Не удалось подтвердить получение");
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleReconciliation = async () => {
    if (!user || !id) return;
    setIsActionLoading(true);
    setActionMessage(null);
    try {
      await requestReconciliation(user.token, id);
      setActionMessage("Запрос сверки отправлен");
    } catch (err) {
      console.error(err);
      setActionMessage("Не удалось отправить запрос сверки");
    } finally {
      setIsActionLoading(false);
    }
  };

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

  if (!settlement) {
    return (
      <div className="empty-state empty-state--full">
        <h2>Settlement не найден</h2>
        <Link className="ghost" to="/payouts">
          Вернуться к списку
        </Link>
      </div>
    );
  }

  const canManage = canManagePayouts(user?.roles);
  const exportLink =
    settlement.payoutBatches?.flatMap((batch) => batch.exportFiles ?? []).find((file) => file.url)?.url ?? null;

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Settlement {settlement.id}</h2>
          <div className="actions">
            <button type="button" className="secondary" onClick={() => setIsSupportOpen(true)}>
              Создать обращение
            </button>
            <Link className="ghost" to="/payouts">
              Назад
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Период</div>
            <div>
              {formatDate(settlement.periodStart)} — {formatDate(settlement.periodEnd)}
            </div>
          </div>
          <div>
            <div className="label">Gross</div>
            <div>{formatCurrency(settlement.grossAmount)}</div>
          </div>
          <div>
            <div className="label">Net</div>
            <div>{formatCurrency(settlement.netAmount)}</div>
          </div>
          <div>
            <div className="label">Статус</div>
            <StatusBadge status={settlement.status} />
          </div>
          <div>
            <div className="label">Кол-во операций</div>
            <div>{formatNumber(settlement.transactionsCount ?? null)}</div>
          </div>
          <div>
            <div className="label">Статус ЭДО</div>
            <div>{settlement.edoStatus ?? "—"}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Действия</h3>
        <div className="actions">
          {exportLink ? (
            <a className="secondary" href={exportLink} target="_blank" rel="noreferrer">
              Download payout export
            </a>
          ) : (
            <button type="button" className="secondary" disabled>
              Download payout export
            </button>
          )}
          <button type="button" className="secondary" disabled={!canManage || isActionLoading} onClick={handleConfirm}>
            Confirm received
          </button>
          <button
            type="button"
            className="secondary"
            disabled={!canManage || isActionLoading}
            onClick={handleReconciliation}
          >
            Request reconciliation
          </button>
        </div>
        {actionMessage ? <p className="muted">{actionMessage}</p> : null}
        {!canManage ? <p className="muted">Действия доступны только владельцу или бухгалтеру.</p> : null}
      </section>

      <section className="card">
        <h3>Breakdown по станциям и продуктам</h3>
        {settlement.breakdowns && settlement.breakdowns.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Станция</th>
                <th>Продукт</th>
                <th>Сумма</th>
                <th>Операции</th>
              </tr>
            </thead>
            <tbody>
              {settlement.breakdowns.map((row, index) => (
                <tr key={`${row.station}-${row.product}-${index}`}>
                  <td>{row.station}</td>
                  <td>{row.product}</td>
                  <td>{formatCurrency(row.amount)}</td>
                  <td>{formatNumber(row.count ?? null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Детализация пока не доступна.</p>
        )}
      </section>

      <section className="card">
        <h3>Комиссии</h3>
        {settlement.commissions && settlement.commissions.length ? (
          <ul className="bullets">
            {settlement.commissions.map((commission) => (
              <li key={commission.label}>
                {commission.label}: {formatCurrency(commission.amount)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Комиссии не рассчитаны.</p>
        )}
      </section>

      <section className="card">
        <h3>Payout batches</h3>
        {settlement.payoutBatches && settlement.payoutBatches.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Статус</th>
                <th>Checksum</th>
              </tr>
            </thead>
            <tbody>
              {settlement.payoutBatches.map((batch) => (
                <tr key={batch.id}>
                  <td>{batch.id}</td>
                  <td>
                    <StatusBadge status={batch.status} />
                  </td>
                  <td>{batch.checksum ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Батчи не связаны.</p>
        )}
      </section>

      <section className="card">
        <h3>Документы</h3>
        {settlement.documents && settlement.documents.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Тип</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {settlement.documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.type}</td>
                  <td>{doc.status}</td>
                  <td>
                    <Link className="link-button" to={`/documents/${doc.id}`}>
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Документы не прикреплены.</p>
        )}
      </section>

      <SupportRequestModal
        isOpen={isSupportOpen}
        onClose={() => setIsSupportOpen(false)}
        subjectType="PAYOUT"
        subjectId={settlement.id}
        defaultTitle={`Проблема с выплатой ${settlement.id}`}
      />
    </div>
  );
}
