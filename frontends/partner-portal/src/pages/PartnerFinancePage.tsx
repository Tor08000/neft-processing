import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  createSettlementChainExport,
  fetchPartnerBalance,
  fetchPartnerExportJobs,
  fetchPartnerLedger,
  fetchPartnerLedgerExplain,
  getPartnerExportDownloadUrl,
} from "../api/partnerFinance";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { StatusBadge } from "../components/StatusBadge";
import { LoadingState } from "../components/states";
import { EmptyState } from "../components/EmptyState";
import { formatCurrency, formatDateTime } from "../utils/format";
import type { PartnerBalance, PartnerExportJob, PartnerLedgerEntry, PartnerLedgerExplain } from "../types/partnerFinance";
import { PartnerErrorState } from "../components/PartnerErrorState";
import { isDemoPartner } from "@shared/demo/demo";
import { DemoEmptyState } from "../components/DemoEmptyState";
import { ApiError } from "../api/http";
import { demoBalance, demoExportJobs, demoLedger, demoLedgerTotals } from "../demo/partnerDemoData";

export function PartnerFinancePage() {
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
  const [isDemoFallback, setIsDemoFallback] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState<unknown>(null);
  const [explainEntry, setExplainEntry] = useState<PartnerLedgerExplain | null>(null);
  const [isExplainOpen, setIsExplainOpen] = useState(false);
  const [exportFrom, setExportFrom] = useState("");
  const [exportTo, setExportTo] = useState("");
  const [exportFormat, setExportFormat] = useState<"CSV" | "ZIP">("CSV");
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportLoading, setExportLoading] = useState(false);

  const currency = useMemo(() => balance?.currency ?? "RUB", [balance]);
  const meta = portal?.partner?.profile?.meta_json ?? {};
  const legalStatus =
    typeof (meta as Record<string, unknown>).legal_status === "string"
      ? ((meta as Record<string, unknown>).legal_status as string)
      : null;
  const needsLegal = Boolean(legalStatus && legalStatus !== "VERIFIED");
  const isDemoPartnerAccount = isDemoPartner(user?.email ?? null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    if (isDemoPartnerAccount) {
      setBalance(demoBalance);
      setLedger(demoLedger);
      setLedgerTotals(demoLedgerTotals);
      setLedgerCursor(null);
      setExportJobs(demoExportJobs);
      setIsDemoFallback(true);
      setError(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
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
        setIsDemoFallback(false);
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiError && isDemoPartnerAccount && (err.status === 403 || err.status === 404)) {
          setBalance(demoBalance);
          setLedger(demoLedger);
          setLedgerTotals(demoLedgerTotals);
          setLedgerCursor(null);
          setExportJobs(demoExportJobs);
          setIsDemoFallback(true);
          setError(null);
          return;
        }
        console.error(err);
        setError(err);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user, isDemoPartnerAccount]);

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
    if (sourceType === "marketplace_order" || sourceType === "partner_order" || sourceType === "order") return `Order ${sourceId ?? entry.order_id ?? "—"}`;
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
            <div className="actions">
              <Link className="ghost" to="/legal">
                Перейти к юридическим данным
              </Link>
            </div>
          </div>
        </section>
      ) : null}
      <section className="card">
        <div className="section-title">
          <h2>Баланс</h2>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <PartnerErrorState error={error} />
        ) : (
          <div className="grid three">
            <div className="metric-card">
              <div className="muted">Доступно</div>
              <strong>{formatCurrency(balance?.balance_available ?? null, currency)}</strong>
            </div>
            <div className="metric-card">
              <div className="muted">Ожидает</div>
              <strong>{formatCurrency(balance?.balance_pending ?? null, currency)}</strong>
            </div>
            <div className="metric-card">
              <div className="muted">Заблокировано</div>
              <strong>{formatCurrency(balance?.balance_blocked ?? null, currency)}</strong>
            </div>
          </div>
        )}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Итоги по счёту</h2>
        </div>
        {ledgerTotals ? (
          <div className="grid three">
            <div className="metric-card">
              <div className="muted">Поступления</div>
              <strong>{formatCurrency(ledgerTotals.in ?? null, currency)}</strong>
            </div>
            <div className="metric-card">
              <div className="muted">Списания</div>
              <strong>{formatCurrency(ledgerTotals.out ?? null, currency)}</strong>
            </div>
            <div className="metric-card">
              <div className="muted">Итого</div>
              <strong>{formatCurrency(ledgerTotals.net ?? null, currency)}</strong>
            </div>
          </div>
        ) : isDemoFallback ? (
          <EmptyState
            title="Нет итогов"
            description="Итоги появятся после операций по счету."
            primaryAction={{ label: "Обновить", onClick: () => window.location.reload() }}
          />
        ) : (
          <EmptyState
            title="Нет итогов"
            description="Итоги появятся после операций по счету."
            primaryAction={{ label: "Обновить", onClick: () => window.location.reload() }}
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
          <PartnerErrorState error={error} />
        ) : ledger.length === 0 ? (
          isDemoFallback ? (
            <EmptyState
              title="Нет движений"
              description="История операций появится после перехода в рабочий контур."
              primaryAction={{ label: "Обновить", onClick: () => window.location.reload() }}
            />
          ) : (
            <EmptyState
              title="Нет движений"
              description="Начисления и списания появятся после завершения заказов."
              primaryAction={{ label: "Обновить", onClick: () => window.location.reload() }}
            />
          )
        ) : (
          <>
            {loadMoreError ? <PartnerErrorState error={loadMoreError} /> : null}
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
                      <button type="button" className="secondary" onClick={() => handleExplain(entry)}>
                        Подробнее
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {ledgerCursor ? (
              <button type="button" className="ghost" onClick={loadMoreLedger} style={{ marginTop: 12 }}>
                Загрузить ещё
              </button>
            ) : null}
          </>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h2>Экспорт расчётов</h2>
        </div>
        {isDemoFallback ? (
          <DemoEmptyState
            title="Экспорт доступен в рабочем контуре"
            description="В демо-режиме экспорт недоступен. В рабочем контуре доступны выгрузки по расчетам."
            primaryAction={{ label: "Обновить", onClick: () => window.location.reload() }}
            secondaryAction={{ label: "Связаться", to: "/support/requests" }}
          />
        ) : (
          <div className="stack">
            <div className="grid three">
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
            <button type="button" className="primary" onClick={handleExport} disabled={!exportFrom || !exportTo || exportLoading}>
              {exportLoading ? "Готовим..." : "Экспортировать расчёты"}
            </button>
            {exportError ? <div className="notice error">{exportError}</div> : null}
            {exportJobs.length ? (
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
                          <a className="link-button" href={getPartnerExportDownloadUrl(job.id)}>
                            Скачать
                          </a>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState
                title="Экспортов пока нет"
                description="Создайте первый экспорт расчетов."
                primaryAction={{ label: "Обновить", onClick: () => window.location.reload() }}
              />
            )}
          </div>
        )}
      </section>

      {isExplainOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="section-title">
              <h3>Расшифровка</h3>
              <button type="button" className="ghost" onClick={() => setIsExplainOpen(false)}>
                Закрыть
              </button>
            </div>
            {explainEntry ? (
              <div className="stack">
                <div className="meta-grid">
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
                  <div>
                    <div className="label">Формула</div>
                    <div className="mono">{explainEntry.formula}</div>
                  </div>
                ) : null}
                {explainEntry.settlement_snapshot_hash ? (
                  <div>
                    <div className="label">Хэш снапшота</div>
                    <div className="mono">{explainEntry.settlement_snapshot_hash}</div>
                  </div>
                ) : null}
                {explainEntry.settlement_breakdown_url ? (
                  <div>
                    <div className="label">Детализация расчёта</div>
                    <a className="link-button" href={explainEntry.settlement_breakdown_url}>
                      Открыть
                    </a>
                  </div>
                ) : null}
              </div>
            ) : (
              <LoadingState />
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
