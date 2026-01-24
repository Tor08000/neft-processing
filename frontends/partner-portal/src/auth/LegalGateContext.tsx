import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { acceptLegalDocument, fetchLegalDocument, fetchLegalRequired } from "../api/legal";
import type { LegalDocumentResponse, LegalRequiredItem, LegalRequiredResponse } from "../api/legal";
import { ApiError } from "../api/http";
import { useAuth } from "./AuthContext";
import { usePortal } from "./PortalContext";

const CACHE_TTL_MS = 60_000;

interface LegalGateContextValue {
  required: LegalRequiredItem[];
  isBlocked: boolean;
  isLoading: boolean;
  isFeatureDisabled: boolean;
  document: LegalDocumentResponse | null;
  loadDocument: (code: string, version: string, locale: string) => Promise<void>;
  refresh: (force?: boolean) => Promise<void>;
  accept: (code: string, version: string, locale: string) => Promise<void>;
}

const LegalGateContext = createContext<LegalGateContextValue | undefined>(undefined);

export const LegalGateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const { portal } = usePortal();
  const navigate = useNavigate();
  const location = useLocation();
  const [required, setRequired] = useState<LegalRequiredItem[]>([]);
  const [isBlocked, setIsBlocked] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isFeatureDisabled, setIsFeatureDisabled] = useState(false);
  const [lastFetched, setLastFetched] = useState<number | null>(null);
  const [document, setDocument] = useState<LegalDocumentResponse | null>(null);
  const onboardingEnabled =
    (import.meta.env.VITE_ONBOARDING_ENABLED ?? "false").toString().toLowerCase() === "1" ||
    (import.meta.env.VITE_ONBOARDING_ENABLED ?? "false").toString().toLowerCase() === "true";
  const onboardingEnabledPortal =
    portal?.gating?.onboarding_enabled ?? portal?.features?.onboarding_enabled ?? onboardingEnabled;

  const refresh = useCallback(
    async (force = false) => {
      if (!user?.token) return;
      if (!onboardingEnabledPortal) {
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
        const data = (await fetchLegalRequired(user.token)) as LegalRequiredResponse;
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
        if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
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
    [lastFetched, onboardingEnabledPortal, user?.token],
  );

  const accept = useCallback(
    async (code: string, version: string, locale: string) => {
      if (!user?.token || !onboardingEnabledPortal || isFeatureDisabled) return;
      setIsLoading(true);
      try {
        const data = await acceptLegalDocument(user.token, { code, version, locale });
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
        if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
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
    [isFeatureDisabled, onboardingEnabledPortal, user?.token],
  );

  const loadDocument = useCallback(
    async (code: string, version: string, locale: string) => {
      if (!user?.token || !onboardingEnabledPortal || isFeatureDisabled) return;
      setIsLoading(true);
      try {
        const data = await fetchLegalDocument(user.token, code, { version, locale });
        setDocument(data);
      } finally {
        setIsLoading(false);
      }
    },
    [isFeatureDisabled, onboardingEnabledPortal, user?.token],
  );

  useEffect(() => {
    if (user?.token) {
      void refresh(true);
    }
  }, [refresh, user?.token]);

  useEffect(() => {
    if (!onboardingEnabledPortal || isFeatureDisabled) {
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
  }, [isFeatureDisabled, location.pathname, navigate, onboardingEnabledPortal, refresh]);

  const value = useMemo(
    () => ({
      required,
      isBlocked,
      isLoading,
      isFeatureDisabled,
      document,
      loadDocument,
      refresh,
      accept,
    }),
    [accept, document, isBlocked, isFeatureDisabled, isLoading, loadDocument, refresh, required],
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
