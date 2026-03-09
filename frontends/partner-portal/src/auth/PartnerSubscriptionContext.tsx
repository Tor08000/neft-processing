import { createContext, useContext, useMemo, useState } from "react";
import type { SubscriptionState } from "@shared/subscriptions/catalog";

type Draft = { selectedPlan?: string | null; subscriptionState?: SubscriptionState };

const KEY = "neft_partner_subscription_draft";
const read = (): Draft => { try { const raw = localStorage.getItem(KEY); return raw ? JSON.parse(raw) as Draft : {}; } catch { return {}; } };

const Ctx = createContext<{ draft: Draft; updateDraft: (patch: Partial<Draft>) => void } | null>(null);

export function PartnerSubscriptionProvider({ children }: { children: React.ReactNode }) {
  const [draft, setDraft] = useState<Draft>(() => read());
  const updateDraft = (patch: Partial<Draft>) => setDraft((prev) => { const next = { ...prev, ...patch }; localStorage.setItem(KEY, JSON.stringify(next)); return next; });
  const value = useMemo(() => ({ draft, updateDraft }), [draft]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const usePartnerSubscription = () => {
  const value = useContext(Ctx);
  if (!value) throw new Error("usePartnerSubscription must be used inside provider");
  return value;
};
