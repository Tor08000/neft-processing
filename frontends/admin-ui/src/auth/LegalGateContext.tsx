import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { acceptLegalDocument, fetchLegalRequired } from "../api/legal";
import { ApiError, ForbiddenError } from "../api/http";
import { useAuth } from "./AuthContext";

const CACHE_TTL_MS = 60_000;

interface LegalRequiredItem {
  code: string;
  title: string;
  locale: string;
  required_version: string;
  published_at: string | null;
  effective_from: string;
  content_hash: string;
  accepted: boolean;
  accepted_at: string | null;
}

type LegalRequiredResponse = {
  required: LegalRequiredItem[];
  is_blocked: boolean;
  enabled?: boolean;
};

interface LegalGateContextValue {
  required: LegalRequiredItem[];
  isBlocked: boolean;
  isLoading: boolean;
  isFeatureDisabled: boolean;
  refresh: (force?: boolean) => Promise<void>;
  accept: (code: string, version: string, locale: string) => Promise<void>;
}

const LegalGateContext = createContext<LegalGateContextValue | undefined>(undefined);

export const LegalGateProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [required, setRequired] = useState<LegalRequiredItem[]>([]);
  const [isBlocked, setIsBlocked] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isFeatureDisabled, setIsFeatureDisabled] = useState(false);
  const [lastFetched, setLastFetched] = useState<number | null>(null);
  const onboardingEnabled =
    (import.meta.env.VITE_ONBOARDING_ENABLED ?? "false").toString().toLowerCase() === "1" ||
    (import.meta.env.VITE_ONBOARDING_ENABLED ?? "false").toString().toLowerCase() === "true";

  const refresh = useCallback(
    async (force = false) => {
      if (!accessToken) return;
      if (!onboardingEnabled) {
        setRequired([]);
        setIsBlocked(false);
        setIsFeatureDisabled(false);
        setLastFetched(Date.now());
        return;
      }
      const now = Date.now();
      if (!force && lastFetched && now - lastFetched < CACHE_TTL_MS) {
        return;
      }
      setIsLoading(true);
      try {
        const data = (await fetchLegalRequired(accessToken)) as LegalRequiredResponse;
        if (data.enabled === false) {
          setRequired([]);
          setIsBlocked(false);
          setIsFeatureDisabled(true);
          setLastFetched(now);
          return;
        }
        setRequired(data.required ?? []);
        setIsBlocked(Boolean(data.is_blocked));
        setLastFetched(now);
        setIsFeatureDisabled(false);
      } catch (error) {
        if (error instanceof ForbiddenError || (error instanceof ApiError && error.status === 404)) {
          setRequired([]);
          setIsBlocked(false);
          setIsFeatureDisabled(true);
          setLastFetched(now);
          return;
        }
      } finally {
        setIsLoading(false);
      }
    },
    [accessToken, lastFetched, onboardingEnabled],
  );

  const accept = useCallback(
    async (code: string, version: string, locale: string) => {
      if (!accessToken || !onboardingEnabled || isFeatureDisabled) return;
      setIsLoading(true);
      try {
        const data = (await acceptLegalDocument(accessToken, { code, version, locale })) as LegalRequiredResponse;
        if (data.enabled === false) {
          setRequired([]);
          setIsBlocked(false);
          setIsFeatureDisabled(true);
          setLastFetched(Date.now());
          return;
        }
        setRequired(data.required ?? []);
        setIsBlocked(Boolean(data.is_blocked));
        setLastFetched(Date.now());
        setIsFeatureDisabled(false);
      } catch (error) {
        if (error instanceof ForbiddenError || (error instanceof ApiError && error.status === 404)) {
          setRequired([]);
          setIsBlocked(false);
          setIsFeatureDisabled(true);
          setLastFetched(Date.now());
          return;
        }
      } finally {
        setIsLoading(false);
      }
    },
    [accessToken, isFeatureDisabled, onboardingEnabled],
  );

  useEffect(() => {
    if (accessToken) {
      void refresh(true);
    }
  }, [accessToken, refresh]);

  useEffect(() => {
    if (!onboardingEnabled || isFeatureDisabled) {
      return;
    }
    const handler = () => {
      void refresh(true);
      if (location.pathname !== "/legal") {
        navigate("/legal", { replace: true });
      }
    };
    window.addEventListener("legal-required", handler);
    return () => window.removeEventListener("legal-required", handler);
  }, [isFeatureDisabled, location.pathname, navigate, onboardingEnabled, refresh]);

  const value = useMemo(
    () => ({ required, isBlocked, isLoading, isFeatureDisabled, refresh, accept }),
    [accept, isBlocked, isFeatureDisabled, isLoading, refresh, required],
  );

  return <LegalGateContext.Provider value={value}>{children}</LegalGateContext.Provider>;
};

export function useLegalGate(): LegalGateContextValue {
  const ctx = useContext(LegalGateContext);
  if (!ctx) {
    throw new Error("useLegalGate must be used within LegalGateProvider");
  }
  return ctx;
}
