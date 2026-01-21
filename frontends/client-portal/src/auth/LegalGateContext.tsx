import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { acceptLegalDocument, fetchLegalDocument, fetchLegalRequired } from "../api/legal";
import { ApiError, UnauthorizedError } from "../api/http";
import type { LegalDocumentResponse, LegalRequiredItem, LegalRequiredResponse } from "../api/legal";
import { useAuth } from "./AuthContext";

const CACHE_TTL_MS = 60_000;

interface LegalGateContextValue {
  required: LegalRequiredItem[];
  isBlocked: boolean;
  isLoading: boolean;
  errorMessage: string | null;
  isFeatureDisabled: boolean;
  document: LegalDocumentResponse | null;
  loadDocument: (code: string, version: string, locale: string) => Promise<void>;
  refresh: (force?: boolean) => Promise<void>;
  accept: (code: string, version: string, locale: string) => Promise<void>;
}

const LegalGateContext = createContext<LegalGateContextValue | undefined>(undefined);

export const LegalGateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [required, setRequired] = useState<LegalRequiredItem[]>([]);
  const [isBlocked, setIsBlocked] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isFeatureDisabled, setIsFeatureDisabled] = useState(false);
  const [lastFetched, setLastFetched] = useState<number | null>(null);
  const [document, setDocument] = useState<LegalDocumentResponse | null>(null);
  const onboardingEnabled =
    (import.meta.env.VITE_ONBOARDING_ENABLED ?? "false").toString().toLowerCase() === "1" ||
    (import.meta.env.VITE_ONBOARDING_ENABLED ?? "false").toString().toLowerCase() === "true";

  const resolveErrorMessage = (error: unknown) => {
    if (error instanceof UnauthorizedError) {
      return "Требуется вход";
    }
    if (error instanceof ApiError && error.status === 403) {
      return "Недостаточно прав";
    }
    if (error instanceof Error) {
      return error.message;
    }
    return "Не удалось загрузить юридические документы";
  };

  const refresh = useCallback(
    async (force = false) => {
      if (!user?.token) return;
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
      setErrorMessage(null);
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
        setErrorMessage(resolveErrorMessage(error));
      } finally {
        setIsLoading(false);
      }
    },
    [lastFetched, onboardingEnabled, user?.token],
  );

  const accept = useCallback(
    async (code: string, version: string, locale: string) => {
      if (!user?.token || !onboardingEnabled || isFeatureDisabled) return;
      setIsLoading(true);
      setErrorMessage(null);
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
        setErrorMessage(resolveErrorMessage(error));
      } finally {
        setIsLoading(false);
      }
    },
    [isFeatureDisabled, onboardingEnabled, user?.token],
  );

  const loadDocument = useCallback(
    async (code: string, version: string, locale: string) => {
      if (!user?.token || !onboardingEnabled || isFeatureDisabled) return;
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const data = await fetchLegalDocument(user.token, code, { version, locale });
        setDocument(data);
      } catch (error) {
        setErrorMessage(resolveErrorMessage(error));
      } finally {
        setIsLoading(false);
      }
    },
    [isFeatureDisabled, onboardingEnabled, user?.token],
  );

  useEffect(() => {
    if (user?.token) {
      void refresh(true);
    }
  }, [refresh, user?.token]);

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
    () => ({
      required,
      isBlocked,
      isLoading,
      errorMessage,
      isFeatureDisabled,
      document,
      loadDocument,
      refresh,
      accept,
    }),
    [accept, document, errorMessage, isBlocked, isFeatureDisabled, isLoading, loadDocument, refresh, required],
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
