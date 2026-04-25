import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerPayoutPreview, fetchPartnerPayouts, requestPartnerPayout } from "../../api/partnerFinance";
import { useAuth } from "../../auth/AuthContext";
import { usePortal } from "../../auth/PortalContext";
import { LoadingState } from "../../components/states";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { formatCurrency, formatDateTime } from "../../utils/format";
import type { PartnerPayoutRequest } from "../../types/partnerFinance";
import { ApiError } from "../../api/http";
import { PartnerErrorState } from "../../components/PartnerErrorState";
import { canOperatePartnerFinance } from "../../access/partnerWorkspace";

export function PayoutsPageProd() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const [amount, setAmount] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [items, setItems] = useState<PartnerPayoutRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [payoutPreview, setPayoutPreview] = useState<{ legal_status?: string | null; warnings?: string[] } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [previewError, setPreviewError] = useState<unknown>(null);
  const canOperate = canOperatePartnerFinance(portal, user?.roles);

  const currency = useMemo(() => "RUB", []);

  const loadPayouts = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchPartnerPayouts(user.token)
      .then((data) => {
        setItems(data.items ?? []);
      })
      .catch((err) => {
        console.error(err);
        setError(err);
      })
      .finally(() => setIsLoading(false));
  };

  const loadPreview = () => {
    if (!user) return;
    setPreviewLoading(true);
    setPreviewError(null);
    fetchPartnerPayoutPreview(user.token)
      .then((data) => {
        setPayoutPreview({ legal_status: data.legal_status, warnings: data.warnings ?? [] });
      })
      .catch((err) => {
        console.error(err);
        setPreviewError(err);
      })
      .finally(() => setPreviewLoading(false));
  };

  useEffect(() => {
    if (!user) return;
    loadPayouts();
  }, [user]);

  useEffect(() => {
    if (!user) return;
    loadPreview();
  }, [user]);

  const handleRequest = async () => {
    if (!user) return;
    if (!canOperate) {
      setSubmitError("Только owner или finance manager может запрашивать выплату.");
      return;
    }
    setSubmitError(null);
    if (!amount || amount <= 0) {
      setSubmitError("Укажите сумму выплаты");
      return;
    }
    setIsSubmitting(true);
    try {
      await requestPartnerPayout(user.token, amount, currency);
      setAmount(0);
      loadPayouts();
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError && err.status === 403) {
        setSubmitError("Профиль не верифицирован. Заполните юридический профиль.");
      } else {
        setSubmitError("Не удалось создать запрос на выплату");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Запросить выплату</h2>
        </div>
        {previewLoading ? <LoadingState label="Проверяем условия выплаты..." /> : null}
        {payoutPreview?.legal_status && payoutPreview.legal_status !== "VERIFIED" ? (
          <div className="notice warning">
            <strong>Выплата заблокирована</strong>
            <div className="muted">Юридический профиль не подтверждён ({payoutPreview.legal_status}).</div>
            <div className="actions">
              <Link className="ghost" to="/legal">
                Завершить юридический профиль
              </Link>
            </div>
          </div>
        ) : null}
        {payoutPreview?.warnings?.length ? (
          <div className="notice warning">
            <strong>Есть предупреждения по профилю</strong>
            <div className="muted">{payoutPreview.warnings.join(", ")}.</div>
            <div className="actions">
              <Link className="ghost" to="/legal">
                Перейти к юридическим данным
              </Link>
            </div>
          </div>
        ) : null}
        {previewError ? (
          <PartnerErrorState
            title="Не удалось проверить условия выплаты"
            description="Проверьте доступность finance owner и повторите запрос."
            error={previewError}
            onRetry={loadPreview}
          />
        ) : null}
        {!canOperate ? (
          <div className="notice">
            <strong>Режим только для чтения</strong>
            <div className="muted">Аналитики видят историю выплат, но не могут создавать новые payout requests.</div>
          </div>
        ) : null}
        <div className="form-grid">
          <label className="field">
            <span className="label">Сумма</span>
            <input
              type="number"
              min={0}
              value={amount}
              onChange={(event) => setAmount(Number(event.target.value))}
              placeholder="0"
            />
          </label>
          <label className="field">
            <span className="label">Валюта</span>
            <input type="text" value={currency} disabled />
          </label>
          <div className="field">
            <button className="primary" type="button" disabled={isSubmitting || !canOperate} onClick={handleRequest}>
              {isSubmitting ? "Отправка..." : "Запросить"}
            </button>
          </div>
        </div>
        {submitError ? (
          <div className="notice error" role="alert">
            {submitError}
          </div>
        ) : null}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>История выплат</h2>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <PartnerErrorState
            title="Не удалось загрузить историю выплат"
            description="Попробуйте обновить список payout requests."
            error={error}
            onRetry={loadPayouts}
          />
        ) : items.length === 0 ? (
          <EmptyState
            title={canOperate ? "Пока нет запросов" : "История выплат пока пуста"}
            description={
              canOperate
                ? "Создайте запрос, чтобы запустить payout workflow."
                : "Когда в этом финансовом разделе появятся payout requests, они будут показаны здесь."
            }
            primaryAction={{ label: "Обновить", onClick: () => loadPayouts() }}
            secondaryAction={
              canOperate
                ? { label: "Создать запрос", onClick: () => window.scrollTo({ top: 0, behavior: "smooth" }) }
                : undefined
            }
          />
        ) : (
          <div className="table-shell">
            <div className="table-scroll">
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
                  {items.map((item) => (
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
            </div>
            <div className="table-footer">
              <div className="table-footer__content muted">Запросов на странице: {items.length}</div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
