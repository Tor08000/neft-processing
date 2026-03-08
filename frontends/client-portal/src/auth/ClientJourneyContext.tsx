import { createContext, useContext, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { isDemoClient } from "@shared/demo/demo";
import { useAuth } from "./AuthContext";
import { useClient } from "./ClientContext";
import { ClientJourneyState, JOURNEY_ROUTE_BY_STATE, JourneyDraft, resolveClientJourneyState } from "./clientJourney";

const STORAGE_KEY = "neft_client_journey_draft";

type ClientJourneyContextValue = {
  state: ClientJourneyState;
  nextRoute: string;
  draft: JourneyDraft;
  updateDraft: (patch: Partial<JourneyDraft>) => void;
  resetDraft: () => void;
  ensureRoute: (source: string) => void;
};

const ClientJourneyContext = createContext<ClientJourneyContextValue | undefined>(undefined);

function readDraft(): JourneyDraft {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as JourneyDraft) : {};
  } catch {
    return {};
  }
}

export function ClientJourneyProvider({ children }: { children: React.ReactNode }) {
  const { authStatus, user } = useAuth();
  const { client, portalState } = useClient();
  const location = useLocation();
  const navigate = useNavigate();
  const [draft, setDraft] = useState<JourneyDraft>(() => readDraft());

  const isDemo = isDemoClient(user?.email ?? client?.user?.email ?? null);
  const state = resolveClientJourneyState({ authStatus, isDemo, client, draft });
  const nextRoute = JOURNEY_ROUTE_BY_STATE[state];

  const updateDraft = (patch: Partial<JourneyDraft>) => {
    setDraft((prev) => {
      const next = { ...prev, ...patch };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  };

  const resetDraft = () => {
    setDraft({});
    localStorage.removeItem(STORAGE_KEY);
  };

  const ensureRoute = (source: string) => {
    if (authStatus !== "authenticated") return;
    const allowedPrefixes = ["/connect", "/dashboard", "/settings", "/client/support", "/documents", "/legal"];
    const isAllowed = allowedPrefixes.some((prefix) => location.pathname.startsWith(prefix));
    if (state !== "ACTIVE" && state !== "DEMO_SHOWCASE" && !isAllowed) {
      if (import.meta.env.DEV) {
        console.info("[journey:redirect]", {
          source,
          currentPath: location.pathname,
          portalState,
          journeyState: state,
          nextRoute,
          isDemo,
        });
      }
      navigate(nextRoute, { replace: true });
    }
  };

  const value = useMemo(
    () => ({ state, nextRoute, draft, updateDraft, resetDraft, ensureRoute }),
    [draft, nextRoute, state],
  );

  return <ClientJourneyContext.Provider value={value}>{children}</ClientJourneyContext.Provider>;
}

export function useClientJourney() {
  const ctx = useContext(ClientJourneyContext);
  if (!ctx) {
    throw new Error("useClientJourney must be used inside ClientJourneyProvider");
  }
  return ctx;
}
