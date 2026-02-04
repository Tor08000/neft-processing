import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerActs, fetchPartnerInvoices } from "../api/partnerFinance";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { StatusBadge } from "../components/StatusBadge";
import { LoadingState } from "../components/states";
import { EmptyState } from "../components/EmptyState";
import { formatCurrency, formatDate } from "../utils/format";
import type { PartnerDocument } from "../types/partnerFinance";
import { PartnerErrorState } from "../components/PartnerErrorState";
import { isDemoPartner } from "@shared/demo/demo";
import { ApiError } from "../api/http";
import { DemoEmptyState } from "../components/DemoEmptyState";
import { demoActs, demoInvoices } from "../demo/partnerDemoData";

export function DocumentsPage() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const [invoices, setInvoices] = useState<PartnerDocument[]>([]);
  const [acts, setActs] = useState<PartnerDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [isDemoFallback, setIsDemoFallback] = useState(false);

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
    setIsLoading(true);
    Promise.all([fetchPartnerInvoices(user.token), fetchPartnerActs(user.token)])
      .then(([invoiceResp, actResp]) => {
        if (!active) return;
        setInvoices(invoiceResp.items ?? []);
        setActs(actResp.items ?? []);
        setIsDemoFallback(false);
      })
      .catch((err) => {
        console.error(err);
        if (!active) return;
        if (err instanceof ApiError && err.status === 404 && isDemoPartnerAccount) {
          setInvoices(demoInvoices);
          setActs(demoActs);
          setIsDemoFallback(true);
          setError(null);
          return;
        }
        setError(err);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user, isDemoPartnerAccount]);

  const renderTable = (items: PartnerDocument[], emptyText: string) => {
    if (items.length === 0) {
      return isDemoFallback ? (
        <DemoEmptyState
          description="В демо-режиме документы доступны только в виде примеров."
          primaryAction={{ label: "Обновить", onClick: () => window.location.reload() }}
          secondaryAction={{ label: "Связаться", to: "/support/requests" }}
        />
      ) : (
        <EmptyState
          title="Документы отсутствуют"
          description={emptyText}
          primaryAction={{ label: "Обновить", onClick: () => window.location.reload() }}
        />
      );
    }
    return (
      <table className="data-table">
        <thead>
          <tr>
            <th>Период</th>
            <th>Сумма</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          {items.map((doc) => (
            <tr key={doc.id}>
              <td>
                {formatDate(doc.period_from)} — {formatDate(doc.period_to)}
              </td>
              <td>{formatCurrency(doc.total_amount ?? null, doc.currency)}</td>
              <td>
                <StatusBadge status={doc.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <div className="stack">
      {needsLegal ? (
        <section className="card">
          <div className="section-title">
            <h2>Документы недоступны</h2>
          </div>
          <div className="notice warning">
            <strong>Юридический профиль не подтверждён</strong>
            <div className="muted">Заполните юридические данные и загрузите документы, чтобы получать акты и счета.</div>
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
          <h2>Счета</h2>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <PartnerErrorState error={error} description="Не удалось загрузить документы" />
        ) : (
          renderTable(invoices, "Новые счета появятся в конце месяца.")
        )}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Акты</h2>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <PartnerErrorState error={error} description="Не удалось загрузить документы" />
        ) : (
          renderTable(acts, "Акты появятся после начислений.")
        )}
      </section>
    </div>
  );
}
