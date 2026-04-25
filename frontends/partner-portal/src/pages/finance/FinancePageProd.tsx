import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  createSettlementChainExport,
  fetchPartnerBalance,
  fetchPartnerExportJobs,
  fetchPartnerLedger,
  fetchPartnerLedgerExplain,
  getPartnerExportDownloadUrl,
} from "../../api/partnerFinance";
import { useAuth } from "../../auth/AuthContext";
import { usePortal } from "../../auth/PortalContext";
import { StatusBadge } from "../../components/StatusBadge";
import { LoadingState } from "../../components/states";
import { EmptyState } from "../../components/EmptyState";
import { formatCurrency, formatDateTime } from "../../utils/format";
import type { PartnerBalance, PartnerExportJob, PartnerLedgerEntry, PartnerLedgerExplain } from "../../types/partnerFinance";
import { PartnerErrorState } from "../../components/PartnerErrorState";
import { DetailPanel, FinanceOverview } from "@shared/brand/components";

export function FinancePageProd() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const [balance, setBalance] = useState<PartnerBalance | null>(null);
  const [ledger, setLedger] = useState<PartnerLedgerEntry[]>([]);
  const [ledgerTotals, setLedgerTotals] = useState<{ in?: number; out?: number; net?: number } | null>(null);
  const [ledgerCursor, setLedgerCursor] = useState<string | null>(null);
  const [ledgerLimit] = useState(20);
  const [exportJobs, setExportJobs] = useState<PartnerExportJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [loadMoreError, setLoadMoreError] = useState<unknown>(null);
  const [explainEntry, setExplainEntry] = useState<PartnerLedgerExplain | null>(null);
  const [isExplainOpen, setIsExplainOpen] = useState(false);
  const [exportFrom, setExportFrom] = useState("");
  const [exportTo, setExportTo] = useState("");
  const [exportFormat, setExportFormat] = useState<"CSV" | "ZIP">("CSV");
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const currency = useMemo(() => balance?.currency ?? "RUB", [balance]);
  const legalStatus = portal?.partner?.legal_state?.status ?? null;
  const needsLegal = Boolean(legalStatus && legalStatus !== "VERIFIED");

  const reloadFinance = () => {
    setReloadKey((value) => value + 1);
  };

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    setError(null);
    setLoadMoreError(null);
    Promise.all([
      fetchPartnerBalance(user.token),
      fetchPartnerLedger(user.token, { limit: ledgerLimit }),
      fetchPartnerExportJobs(user.token),
    ])
      .then(([balanceResp, ledgerResp, exportResp]) => {
        if (!active) return;
        setBalance(balanceResp);
        setLedger(ledgerResp.items ?? []);
        setLedgerTotals(ledgerResp.totals ?? null);
        setLedgerCursor(ledgerResp.next_cursor ?? null);
        setExportJobs(exportResp.items ?? []);
      })
      .catch((err) => {
        if (!active) return;
        console.error(err);
        setError(err);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user, ledgerLimit, reloadKey]);

  const handleExplain = async (entry: PartnerLedgerEntry) => {
    if (!user) return;
    setExplainEntry(null);
    setIsExplainOpen(true);
    try {
      const data = await fetchPartnerLedgerExplain(user.token, entry.id);
      setExplainEntry(data);
    } catch (err) {
      console.error(err);
      setExplainEntry({
        entry_id: entry.id,
        operation: entry.entry_type,
        amount: entry.amount,
        currency: entry.currency,
        direction: entry.direction,
        source_label: "Не удалось загрузить объяснение",
      });
    }
  };

  const loadMoreLedger = async () => {
    if (!user || !ledgerCursor) return;
    setLoadMoreError(null);
    try {
      const next = await fetchPartnerLedger(user.token, { limit: ledgerLimit, cursor: ledgerCursor });
      setLedger((prev) => [...prev, ...(next.items ?? [])]);
      setLedgerCursor(next.next_cursor ?? null);
    } catch (err) {
      console.error(err);
      setLoadMoreError(err);
    }
  };

  const handleExport = async () => {
    if (!user || !exportFrom || !exportTo) return;
    setExportError(null);
    setExportLoading(true);
    try {
      const result = await createSettlementChainExport(user.token, { from: exportFrom, to: exportTo, format: exportFormat });
      const updated = await fetchPartnerExportJobs(user.token);
      setExportJobs(updated.items ?? []);
      setExportLoading(false);
      setExportError(result.status === "FAILED" ? "Экспорт не создан" : null);
    } catch (err) {
      console.error(err);
      setExportError("Не удалось запустить экспорт");
      setExportLoading(false);
    }
  };

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

  return (
    <div className="stack">
      {needsLegal ? (
        <section className="card">
          <div className="section-title">
            <h2>Блокировки выплат</h2>
          </div>
          <div className="notice warning">
            <strong>Юридический профиль не подтверждён</strong>
            <div className="muted">Заполните юридические данные и загрузите документы для разблокировки выплат.</div>
            <div className="toolbar-actions">
              <Link className="ghost" to="/legal">
                Перейти к юридическим данным
              </Link>
            </div>
          </div>
        </section>
      ) : null}
      <section className="card">
        <div className="section-title">
          <h2>Read-only finance registers</h2>
        </div>
        <div className="toolbar-actions">
          <Link className="ghost" to="/contracts">
            Contracts
          </Link>
          <Link className="ghost" to="/settlements">
            Settlements
          </Link>
        </div>
        <p className="muted small">
          Contracts and settlement periods are read-only views over the finance owner. Payout approval stays in the existing admin workflow.
        </p>
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Баланс</h2>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <PartnerErrorState error={error} onRetry={reloadFinance} />
        ) : (
          <FinanceOverview
            items={[
              {
                id: "available",
                label: "Доступно",
                value: formatCurrency(balance?.balance_available ?? null, currency),
                tone: "success",
              },
              {
                id: "pending",
                label: "Ожидает",
                value: formatCurrency(balance?.balance_pending ?? null, currency),
                tone: "warning",
              },
              {
                id: "blocked",
                label: "Заблокировано",
                value: formatCurrency(balance?.balance_blocked ?? null, currency),
                tone: "danger",
              },
            ]}
          />
        )}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Итоги по счёту</h2>
        </div>
        {ledgerTotals ? (
          <FinanceOverview
            items={[
              {
                id: "ledger-in",
                label: "Поступления",
                value: formatCurrency(ledgerTotals.in ?? null, currency),
                tone: "success",
              },
              {
                id: "ledger-out",
                label: "Списания",
                value: formatCurrency(ledgerTotals.out ?? null, currency),
                tone: "warning",
              },
              {
                id: "ledger-net",
                label: "Итого",
                value: formatCurrency(ledgerTotals.net ?? null, currency),
                tone: "info",
              },
            ]}
          />
        ) : (
          <EmptyState
            title="Нет итогов"
            description="Итоги появятся после операций по счету."
            primaryAction={{ label: "Обновить", onClick: reloadFinance }}
          />
        )}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Движения по счёту</h2>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <PartnerErrorState error={error} onRetry={reloadFinance} />
        ) : ledger.length === 0 ? (
          <EmptyState
            title="Нет движений"
            description="Начисления и списания появятся после завершения заказов."
            primaryAction={{ label: "Обновить", onClick: reloadFinance }}
          />
        ) : (
          <div className="table-shell">
            {loadMoreError ? <PartnerErrorState error={loadMoreError} onRetry={loadMoreLedger} /> : null}
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Тип</th>
                    <th>Сумма</th>
                    <th>Направление</th>
                    <th>Заказ</th>
                    <th>Источник</th>
                    <th>Расшифровка</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.map((entry) => (
                    <tr key={entry.id}>
                      <td>{formatDateTime(entry.created_at)}</td>
                      <td>
                        <StatusBadge status={entry.entry_type} />
                      </td>
                      <td>{formatCurrency(entry.amount ?? null, entry.currency)}</td>
                      <td>{entry.direction}</td>
                      <td className="mono">{entry.order_id ?? "—"}</td>
                      <td>{resolveLedgerSource(entry)}</td>
                      <td>
                        <div className="table-row-actions">
                          <button type="button" className="secondary" onClick={() => handleExplain(entry)}>
                            Подробнее
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <div className="table-footer__content">
                <span className="muted">Проводок: {ledger.length}</span>
                {ledgerCursor ? (
                  <div className="toolbar-actions">
                    <button type="button" className="ghost" onClick={loadMoreLedger}>
                      Загрузить ещё
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h2>Экспорт расчётов</h2>
        </div>
        <div className="stack">
          <div className="surface-toolbar">
            <div className="grid three" style={{ flex: "1 1 560px" }}>
              <label className="form-field">
                Период с
                <input type="date" value={exportFrom} onChange={(event) => setExportFrom(event.target.value)} />
              </label>
              <label className="form-field">
                Период по
                <input type="date" value={exportTo} onChange={(event) => setExportTo(event.target.value)} />
              </label>
              <label className="form-field">
                Формат
                <select value={exportFormat} onChange={(event) => setExportFormat(event.target.value as "CSV" | "ZIP")}>
                  <option value="CSV">CSV</option>
                  <option value="ZIP">ZIP</option>
                </select>
              </label>
            </div>
            <div className="toolbar-actions">
              <button type="button" className="primary" onClick={handleExport} disabled={!exportFrom || !exportTo || exportLoading}>
                {exportLoading ? "Готовим..." : "Экспортировать расчёты"}
              </button>
            </div>
          </div>
          {exportError ? <div className="notice error">{exportError}</div> : null}
          {exportJobs.length ? (
            <div className="table-shell">
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Файл</th>
                      <th>Статус</th>
                      <th>Создано</th>
                      <th>Скачать</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exportJobs.map((job) => (
                      <tr key={job.id}>
                        <td>{job.file_name ?? job.id}</td>
                        <td>{job.status}</td>
                        <td>{formatDateTime(job.created_at)}</td>
                        <td>
                          {job.status === "DONE" ? (
                            <div className="table-row-actions">
                              <a className="link-button" href={getPartnerExportDownloadUrl(job.id)}>
                                Скачать
                              </a>
                            </div>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="table-footer">
                <div className="table-footer__content">
                  <span className="muted">Экспортов: {exportJobs.length}</span>
                </div>
              </div>
            </div>
          ) : (
            <EmptyState
              title="Экспортов пока нет"
              description="Создайте первый экспорт расчетов."
              primaryAction={{ label: "Обновить", onClick: reloadFinance }}
            />
          )}
        </div>
      </section>

      <DetailPanel
        open={isExplainOpen}
        title="Расшифровка"
        subtitle={explainEntry?.entry_id ? `Entry ${explainEntry.entry_id}` : "Загрузка деталей проводки"}
        onClose={() => setIsExplainOpen(false)}
        closeLabel="Закрыть"
        size="md"
      >
        {explainEntry ? (
          <div className="stack">
            <div className="detail-panel__card meta-grid">
              <div>
                <div className="label">Операция</div>
                <div>{explainEntry.operation}</div>
              </div>
              <div>
                <div className="label">Сумма</div>
                <div>{formatCurrency(explainEntry.amount, explainEntry.currency)}</div>
              </div>
              <div>
                <div className="label">Направление</div>
                <div>{explainEntry.direction}</div>
              </div>
              <div>
                <div className="label">Источник</div>
                <div>{explainEntry.source_label ?? "—"}</div>
              </div>
              <div>
                <div className="label">Администратор</div>
                <div className="mono">{explainEntry.admin_actor_id ?? "—"}</div>
              </div>
            </div>
            {explainEntry.formula ? (
              <div className="detail-panel__card">
                <div className="label">Формула</div>
                <div className="mono">{explainEntry.formula}</div>
              </div>
            ) : null}
            {explainEntry.settlement_snapshot_hash ? (
              <div className="detail-panel__card">
                <div className="label">Хэш снапшота</div>
                <div className="mono">{explainEntry.settlement_snapshot_hash}</div>
              </div>
            ) : null}
            {explainEntry.settlement_breakdown_url ? (
              <div className="detail-panel__card">
                <div className="label">Детализация расчёта</div>
                <div className="toolbar-actions">
                  <a className="link-button" href={explainEntry.settlement_breakdown_url}>
                    Открыть
                  </a>
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <LoadingState />
        )}
      </DetailPanel>
    </div>
  );
}
