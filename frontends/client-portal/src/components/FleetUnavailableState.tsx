import { useState } from "react";
import { AppEmptyState } from "./states";
import { useAuth } from "../auth/AuthContext";
import { demoFleetUsers, demoLimits, demoReports } from "../demo/demoData";
import { useI18n } from "../i18n";
import { isDemoClient } from "@shared/demo/demo";

export function FleetUnavailableState() {
  const { user } = useAuth();
  const { t } = useI18n();
  const isDemoClientAccount = isDemoClient(user?.email ?? null);
  const [showDemoData, setShowDemoData] = useState(false);

  if (isDemoClientAccount) {
    return (
      <div className="stack">
        <div className="notice">Демо-режим: автопарк доступен в корпоративном тарифе или рабочем контуре.</div>
        <AppEmptyState
          title="Функции автопарка доступны в корпоративном тарифе"
          description="В проде здесь будут пользователи автопарка, лимиты и отчётность."
          action={
            <button type="button" className="secondary neft-btn-secondary" onClick={() => setShowDemoData((prev) => !prev)}>
              {showDemoData ? "Скрыть демо-данные" : "Посмотреть демо-данные"}
            </button>
          }
        />
        {showDemoData ? (
          <div className="grid three">
            <section className="card">
              <h3>Пользователи автопарка</h3>
              <ul className="list">
                {demoFleetUsers.map((userItem) => (
                  <li key={userItem.id}>
                    <div>{userItem.email}</div>
                    <div className="muted small">
                      {userItem.role} · {userItem.status}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
            <section className="card">
              <h3>Лимиты</h3>
              <ul className="list">
                {demoLimits.map((limit) => (
                  <li key={limit.id}>
                    <div>{limit.scope}</div>
                    <div className="muted small">
                      {limit.period} · {limit.amount.toLocaleString("ru-RU")} ₽ · {limit.status}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
            <section className="card">
              <h3>Отчёты</h3>
              <ul className="list">
                {demoReports.map((report) => (
                  <li key={report.id}>
                    <div>{report.title}</div>
                    <div className="muted small">
                      {report.period} · {report.status}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        ) : null}
      </div>
    );
  }
  return <AppEmptyState title={t("fleet.errors.unavailableTitle")} description={t("fleet.errors.unavailableDescription")} />;
}
