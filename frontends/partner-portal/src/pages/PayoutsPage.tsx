import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerPayoutPreview, fetchPartnerPayouts, requestPartnerPayout } from "../api/partnerFinance";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatDateTime } from "../utils/format";
import type { PartnerPayoutRequest } from "../types/partnerFinance";
import { ApiError } from "../api/http";

export function PayoutsPage() {
  const { user } = useAuth();
  const [amount, setAmount] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [items, setItems] = useState<PartnerPayoutRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [payoutPreview, setPayoutPreview] = useState<{ legal_status?: string | null; warnings?: string[] } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const currency = useMemo(() => "RUB", []);

  const loadPayouts = () => {
    if (!user) return;
    setIsLoading(true);
    fetchPartnerPayouts(user.token)
      .then((data) => setItems(data.items ?? []))
      .catch((err) => {
        console.error(err);
        setError("Не удалось загрузить историю выплат");
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    if (!user) return;
    loadPayouts();
  }, [user]);

  useEffect(() => {
    if (!user) return;
    setPreviewError(null);
    fetchPartnerPayoutPreview(user.token)
      .then((data) => setPayoutPreview({ legal_status: data.legal_status, warnings: data.warnings ?? [] }))
      .catch((err) => {
        console.error(err);
        setPreviewError("Не удалось загрузить статус выплат");
      });
  }, [user]);

  const handleRequest = async () => {
    if (!user) return;
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
        {previewError ? <div className="error">{previewError}</div> : null}
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
            <button className="primary" type="button" disabled={isSubmitting} onClick={handleRequest}>
              {isSubmitting ? "Отправка..." : "Запросить"}
            </button>
          </div>
        </div>
        {submitError ? <div className="error">{submitError}</div> : null}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>История выплат</h2>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState description={error} />
        ) : items.length === 0 ? (
          <div className="empty-state">
            <strong>Пока нет запросов</strong>
            <span className="muted">Создайте запрос, чтобы получить выплату.</span>
          </div>
        ) : (
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
        )}
      </section>
    </div>
  );
}
