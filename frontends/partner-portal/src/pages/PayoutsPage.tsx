import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerPayoutPreview, fetchPartnerPayouts, requestPartnerPayout } from "../api/partnerFinance";
import { useAuth } from "../auth/AuthContext";
import { LoadingState } from "../components/states";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatDateTime } from "../utils/format";
import type { PartnerPayoutRequest } from "../types/partnerFinance";
import { ApiError } from "../api/http";
import { PartnerErrorState } from "../components/PartnerErrorState";
import { isDemoPartner } from "@shared/demo/demo";
import { DemoEmptyState } from "../components/DemoEmptyState";
import { demoPayouts } from "../demo/partnerDemoData";

export function PayoutsPage() {
  const { user } = useAuth();
  const [amount, setAmount] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [items, setItems] = useState<PartnerPayoutRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [payoutPreview, setPayoutPreview] = useState<{ legal_status?: string | null; warnings?: string[] } | null>(null);
  const [previewError, setPreviewError] = useState<unknown>(null);

  const currency = useMemo(() => "RUB", []);
  const isDemoPartnerAccount = isDemoPartner(user?.email ?? null);

  const loadPayouts = () => {
    if (!user) return;
    if (isDemoPartnerAccount) {
      setItems(demoPayouts);
      setError(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    fetchPartnerPayouts(user.token)
      .then((data) => {
        setItems(data.items ?? []);
      })
      .catch((err) => {
        console.error(err);
        if (err instanceof ApiError && isDemoPartnerAccount && (err.status === 403 || err.status === 404)) {
          setItems([]);
          setError(null);
          return;
        }
        setError(err);
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    if (!user) return;
    loadPayouts();
  }, [user, isDemoPartnerAccount]);

  useEffect(() => {
    if (!user) return;
    if (isDemoPartnerAccount) {
      setPayoutPreview({ legal_status: "VERIFIED", warnings: [] });
      setPreviewError(null);
      return;
    }
    setPreviewError(null);
    fetchPartnerPayoutPreview(user.token)
      .then((data) => {
        setPayoutPreview({ legal_status: data.legal_status, warnings: data.warnings ?? [] });
      })
      .catch((err) => {
        console.error(err);
        if (err instanceof ApiError && isDemoPartnerAccount && (err.status === 403 || err.status === 404)) {
          setPayoutPreview({ legal_status: "VERIFIED", warnings: [] });
          setPreviewError(null);
          return;
        }
        setPreviewError(err);
      });
  }, [user, isDemoPartnerAccount]);

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
        {isDemoPartnerAccount ? (
          <div className="notice">
            <div>В демо-режиме запросы на выплату недоступны.</div>
          </div>
        ) : null}
        {previewError ? <PartnerErrorState error={previewError} /> : null}
        <div className="form-grid">
          <label className="field">
            <span className="label">Сумма</span>
            <input
              type="number"
              min={0}
              value={amount}
              onChange={(event) => setAmount(Number(event.target.value))}
              placeholder="0"
              disabled={isDemoPartnerAccount}
            />
          </label>
          <label className="field">
            <span className="label">Валюта</span>
            <input type="text" value={currency} disabled />
          </label>
          <div className="field">
            <button
              className="primary"
              type="button"
              disabled={isSubmitting || isDemoPartnerAccount}
              onClick={handleRequest}
              title={isDemoPartnerAccount ? "Доступно в рабочем контуре" : undefined}
            >
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
          <PartnerErrorState error={error} />
        ) : isDemoPartnerAccount && items.length ? (
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
        ) : isDemoPartnerAccount ? (
          <DemoEmptyState
            primaryAction={{ label: "Обновить", onClick: () => loadPayouts() }}
            secondaryAction={{ label: "Связаться", to: "/support/requests" }}
          />
        ) : items.length === 0 ? (
          <EmptyState
            title="Пока нет запросов"
            description="Создайте запрос, чтобы получить выплату."
            primaryAction={{ label: "Обновить", onClick: () => loadPayouts() }}
            secondaryAction={{ label: "Создать запрос", onClick: () => window.scrollTo({ top: 0, behavior: "smooth" }) }}
          />
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
