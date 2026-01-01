import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { fetchGamificationSummary, fetchMySubscription, fetchSubscriptionBenefits } from "../api/subscriptions";
import type { ClientSubscription, GamificationSummary, SubscriptionBenefits } from "../types/subscriptions";
import { useI18n } from "../i18n";

export function SubscriptionPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [subscription, setSubscription] = useState<ClientSubscription | null>(null);
  const [benefits, setBenefits] = useState<SubscriptionBenefits | null>(null);
  const [gamification, setGamification] = useState<GamificationSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchMySubscription(user), fetchSubscriptionBenefits(user), fetchGamificationSummary(user)])
      .then(([subscriptionResponse, benefitsResponse, gamificationResponse]) => {
        setSubscription(subscriptionResponse);
        setBenefits(benefitsResponse);
        setGamification(gamificationResponse);
      })
      .finally(() => setLoading(false));
  }, [user]);

  const disabledModules = benefits?.unavailable_modules ?? [];
  const enabledModules = benefits?.modules ?? [];
  const getRecordString = (value: unknown, key: string): string | undefined => {
    if (!value || typeof value !== "object") return undefined;
    const record = value as Record<string, unknown>;
    const candidate = record[key];
    return typeof candidate === "string" ? candidate : undefined;
  };
  const previewModules = gamification?.preview?.modules as
    | { module_code: string; enabled: boolean; tier?: string | null }[]
    | undefined;
  const previewAvailable = gamification?.preview?.available as
    | { achievements?: { title: string }[]; streaks?: { title: string }[]; bonuses?: { title: string }[] }
    | undefined;

  const savings = useMemo(() => {
    if (!gamification?.bonuses?.length) return t("subscription.savingsFallback");
    return t("subscription.savingsValue", { value: gamification.bonuses.length });
  }, [gamification, t]);

  if (loading) {
    return <div>{t("common.loading")}</div>;
  }

  if (!subscription || !benefits) {
    return <div>{t("subscription.empty")}</div>;
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <section className="card" style={{ padding: 16 }}>
        <h2>{t("subscription.title")}</h2>
        <div style={{ display: "grid", gap: 8 }}>
          <div>
            {t("subscription.currentPlan")}: <strong>{subscription.plan?.title ?? subscription.plan_id}</strong>
          </div>
          <div>
            {t("subscription.status")}: <strong>{subscription.status}</strong>
          </div>
          <div>
            {t("subscription.period")}:
            <strong>
              {subscription.start_at} → {subscription.end_at ?? t("common.notAvailable")}
            </strong>
          </div>
        </div>
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.includes")}</h3>
        <ul>
          {enabledModules.map((module) => (
            <li key={module.module_code}>
              {module.module_code} · {t("subscription.active")}
            </li>
          ))}
        </ul>
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.unavailable")}</h3>
        {disabledModules.length ? (
          <ul>
            {disabledModules.map((module) => (
              <li key={module.module_code} style={{ opacity: 0.6 }}>
                {module.module_code} · {t("subscription.availableInPro")}
              </li>
            ))}
          </ul>
        ) : (
          <div>{t("subscription.allEnabled")}</div>
        )}
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.savingsTitle")}</h3>
        <div>{savings}</div>
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.bonuses")}</h3>
        {gamification?.bonuses?.length ? (
          <ul>
            {gamification.bonuses.map((bonus, index) => {
              const title = getRecordString(bonus, "title");
              return <li key={index}>{title ?? t("subscription.bonusUnlocked")}</li>;
            })}
          </ul>
        ) : (
          <div>{t("subscription.bonusesEmpty")}</div>
        )}
        {gamification?.preview && subscription.status === "FREE" ? (
          <div style={{ marginTop: 12 }}>
            <strong>{t("subscription.previewTitle")}</strong>
            <div>
              {t("subscription.previewSubtitle", {
                plan: getRecordString(gamification.preview, "plan_title") ?? t("common.notAvailable"),
              })}
            </div>
            {previewModules ? (
              <ul>
                {previewModules.map((module, index) => (
                  <li key={`${module.module_code}-${index}`}>{module.module_code}</li>
                ))}
              </ul>
            ) : null}
            {previewAvailable?.bonuses?.length ? (
              <div style={{ marginTop: 8 }}>{t("subscription.availableByPlan")}</div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.streaks")}</h3>
        {gamification?.streaks?.length ? (
          <ul>
            {gamification.streaks.map((streak, index) => {
              const title = getRecordString(streak, "title");
              return <li key={index}>{title ?? t("subscription.streakActive")}</li>;
            })}
          </ul>
        ) : (
          <div>{t("subscription.streaksEmpty")}</div>
        )}
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.achievements")}</h3>
        {gamification?.achievements?.length ? (
          <ul>
            {gamification.achievements.map((achievement, index) => {
              const title = getRecordString(achievement, "title");
              return <li key={index}>{title ?? t("subscription.achievementUnlocked")}</li>;
            })}
          </ul>
        ) : (
          <div>{t("subscription.achievementsEmpty")}</div>
        )}
        {subscription.status === "FREE" && previewAvailable?.achievements?.length ? (
          <div style={{ marginTop: 8 }}>{t("subscription.availableByPlan")}</div>
        ) : null}
      </section>
    </div>
  );
}

export default SubscriptionPage;
