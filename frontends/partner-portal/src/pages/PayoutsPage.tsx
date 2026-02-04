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
import { demoPayouts } from "../demo/partnerDemoData";
import { isDemoPartner } from "@shared/demo/demo";
import { DemoEmptyState } from "../components/DemoEmptyState";

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
  const [isDemoFallback, setIsDemoFallback] = useState(false);

  const currency = useMemo(() => "RUB", []);
  const isDemoPartnerAccount = isDemoPartner(user?.email ?? null);

  const loadPayouts = () => {
    if (!user) return;
    setIsLoading(true);
    fetchPartnerPayouts(user.token)
      .then((data) => {
        setItems(data.items ?? []);
        setIsDemoFallback(false);
      })
      .catch((err) => {
        console.error(err);
        if (err instanceof ApiError && err.status === 404 && isDemoPartnerAccount) {
          setItems(demoPayouts);
          setIsDemoFallback(true);
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
    setPreviewError(null);
    fetchPartnerPayoutPreview(user.token)
      .then((data) => {
        setPayoutPreview({ legal_status: data.legal_status, warnings: data.warnings ?? [] });
        setIsDemoFallback(false);
      })
      .catch((err) => {
        console.error(err);
        if (err instanceof ApiError && err.status === 404 && isDemoPartnerAccount) {
          setPayoutPreview({ legal_status: "VERIFIED", warnings: [] });
          setIsDemoFallback(true);
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
    if (isDemoPartnerAccount && isDemoFallback) {
      setItems((prev) => [
        {
          id: `demo-${Date.now()}`,
          partner_org_id: "demo-partner",
          amount,
          currency,
          status: "PENDING",
          created_at: new Date().toISOString(),
        },
        ...prev,
      ]);
      setAmount(0);
      setIsSubmitting(false);
      return;
    }
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
        {isDemoFallback ? (
          <div className="notice">
            <div>В демо-режиме выплаты доступны в ограниченном виде.</div>
          </div>
        ) : null}
        {previewError ? <PartnerErrorState error={previewError} description="Не удалось загрузить статус выплат" /> : null}
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
          <PartnerErrorState error={error} description="Не удалось загрузить историю выплат" />
        ) : items.length === 0 ? (
          isDemoFallback ? (
            <DemoEmptyState
              description="В демо-режиме история выплат не заполняется реальными данными."
              primaryAction={{ label: "Обновить", onClick: () => loadPayouts() }}
              secondaryAction={{ label: "Связаться", to: "/support/requests" }}
            />
          ) : (
            <EmptyState
              title="Пока нет запросов"
              description="Создайте запрос, чтобы получить выплату."
              primaryAction={{ label: "Обновить", onClick: () => loadPayouts() }}
              secondaryAction={{ label: "Создать запрос", onClick: () => window.scrollTo({ top: 0, behavior: "smooth" }) }}
            />
          )
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
