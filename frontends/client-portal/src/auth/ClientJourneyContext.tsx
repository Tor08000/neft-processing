import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { isDemoClient } from "@shared/demo/demo";
import { useAuth } from "./AuthContext";
import { useClient } from "./ClientContext";
import { ClientJourneyState, JOURNEY_ROUTE_BY_STATE, JourneyDraft, resolveClientJourneyState } from "./clientJourney";

const STORAGE_KEY = "neft_client_journey_draft";
const DEBUG_CLIENT_JOURNEY = Boolean(import.meta.env.DEV && import.meta.env.VITE_CLIENT_DEBUG_JOURNEY === "true");

const CANONICAL_ONBOARDING_ROUTES = new Set([
  "/onboarding",
  "/onboarding/plan",
  "/onboarding/contract",
]);

const CONNECT_COMPATIBILITY_ROUTES = new Set([
  "/connect",
  "/connect/plan",
  "/connect/type",
  "/connect/profile",
  "/connect/documents",
  "/connect/sign",
  "/connect/payment",
]);

const JOURNEY_ALLOWED_ROUTES = new Set([...CANONICAL_ONBOARDING_ROUTES, ...CONNECT_COMPATIBILITY_ROUTES]);
const LIMITED_CABINET_ROUTES = ["/dashboard", "/settings", "/client/support", "/documents", "/client/documents", "/legal", "/subscription"];

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

  const updateDraft = useCallback((patch: Partial<JourneyDraft>) => {
    setDraft((prev) => {
      const next = { ...prev, ...patch };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const resetDraft = useCallback(() => {
    setDraft({});
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const ensureRoute = useCallback(
    (source: string) => {
      if (authStatus !== "authenticated") return;
      if (!isDemo && portalState !== "READY") return;

      const pathname = location.pathname;
      const isLimitedRoute = LIMITED_CABINET_ROUTES.some((prefix) => pathname.startsWith(prefix));
      const isJourneyRoute = JOURNEY_ALLOWED_ROUTES.has(pathname);
      const isAllowedWhileConnecting = isLimitedRoute || isJourneyRoute;

      if (state === "DEMO_SHOWCASE" || state === "ACTIVE") {
        if (JOURNEY_ALLOWED_ROUTES.has(pathname)) {
          navigate("/dashboard", { replace: true });
        }
        return;
      }

      if (!isAllowedWhileConnecting && pathname !== nextRoute) {
        if (DEBUG_CLIENT_JOURNEY) {
          console.info("[journey:redirect]", {
            source,
            currentPath: pathname,
            portalState,
            journeyState: state,
            nextRoute,
            isDemo,
          });
        }
        navigate(nextRoute, { replace: true });
      }
    },
    [authStatus, isDemo, location.pathname, navigate, nextRoute, portalState, state],
  );

  const value = useMemo(
    () => ({ state, nextRoute, draft, updateDraft, resetDraft, ensureRoute }),
    [draft, ensureRoute, nextRoute, resetDraft, state, updateDraft],
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
