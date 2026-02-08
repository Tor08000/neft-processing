import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { acceptLegalDocument, fetchLegalDocument, fetchLegalRequired } from "../api/legal";
import type { LegalDocumentResponse, LegalRequiredItem, LegalRequiredResponse } from "../api/legal";
import { ApiError } from "../api/http";
import { useAuth } from "./AuthContext";
import { usePortal } from "./PortalContext";

const CACHE_TTL_MS = 300_000;

interface LegalGateContextValue {
  required: LegalRequiredItem[];
  isBlocked: boolean;
  isLoading: boolean;
  isFeatureDisabled: boolean;
  error: ApiError | null;
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
  const [requiredLoadedAt, setRequiredLoadedAt] = useState<number | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [document, setDocument] = useState<LegalDocumentResponse | null>(null);
  const isLoadingRef = useRef(false);
  const requiredLoadedAtRef = useRef<number | null>(null);
  const tokenRef = useRef<string | null>(user?.token ?? null);
  const refreshRef = useRef<(force?: boolean) => Promise<void>>(() => Promise.resolve());
  const onboardingEnabled =
    (import.meta.env.VITE_ONBOARDING_ENABLED ?? "false").toString().toLowerCase() === "1" ||
    (import.meta.env.VITE_ONBOARDING_ENABLED ?? "false").toString().toLowerCase() === "true";
  const onboardingEnabledPortal =
    portal?.gating?.onboarding_enabled ?? portal?.features?.onboarding_enabled ?? onboardingEnabled;

  const updateRequiredLoadedAt = useCallback((value: number | null) => {
    requiredLoadedAtRef.current = value;
    setRequiredLoadedAt(value);
  }, []);

  const fetchRequiredOnce = useCallback(
    async (force = false) => {
      const token = tokenRef.current;
      if (!token || isLoadingRef.current) return;
      if (!onboardingEnabledPortal) {
        setRequired([]);
        setIsBlocked(false);
        setIsFeatureDisabled(false);
        setError(null);
        updateRequiredLoadedAt(Date.now());
        return;
      }
      const now = Date.now();
      const loadedAt = requiredLoadedAtRef.current;
      if (!force && loadedAt && now - loadedAt < CACHE_TTL_MS) {
        return;
      }
      setIsLoading(true);
      isLoadingRef.current = true;
      setError(null);
      try {
        const data = (await fetchLegalRequired(token)) as LegalRequiredResponse;
        if (data.enabled === false) {
          setRequired([]);
          setIsBlocked(false);
          setIsFeatureDisabled(true);
          updateRequiredLoadedAt(now);
          return;
        }
        setRequired(data.required ?? []);
        setIsBlocked(Boolean(data.is_blocked));
        updateRequiredLoadedAt(now);
        setIsFeatureDisabled(false);
      } catch (err) {
        if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
          setRequired([]);
          setIsBlocked(false);
          setIsFeatureDisabled(true);
          updateRequiredLoadedAt(now);
          return;
        }
        if (err instanceof ApiError) {
          setError(err);
        }
      } finally {
        setIsLoading(false);
        isLoadingRef.current = false;
      }
    },
    [onboardingEnabledPortal, updateRequiredLoadedAt],
  );

  const refresh = useCallback(
    async (force = false) => {
      if (force) {
        updateRequiredLoadedAt(null);
      }
      await fetchRequiredOnce(force);
    },
    [fetchRequiredOnce, updateRequiredLoadedAt],
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
          updateRequiredLoadedAt(Date.now());
          return;
        }
        setRequired(data.required ?? []);
        setIsBlocked(Boolean(data.is_blocked));
        updateRequiredLoadedAt(Date.now());
        setIsFeatureDisabled(false);
      } catch (error) {
        if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
          setRequired([]);
          setIsBlocked(false);
          setIsFeatureDisabled(true);
          updateRequiredLoadedAt(Date.now());
          return;
        }
      } finally {
        setIsLoading(false);
      }
    },
    [isFeatureDisabled, onboardingEnabledPortal, updateRequiredLoadedAt, user?.token],
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
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    tokenRef.current = user?.token ?? null;
    if (!user?.token) {
      updateRequiredLoadedAt(null);
      setRequired([]);
      setIsBlocked(false);
      setIsFeatureDisabled(false);
      setError(null);
      return;
    }
    if (requiredLoadedAtRef.current && requiredLoadedAtRef.current < Date.now() - CACHE_TTL_MS) {
      updateRequiredLoadedAt(null);
    }
    void refreshRef.current(false);
  }, [user?.token]);

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
      error,
      document,
      loadDocument,
      refresh,
      accept,
    }),
    [accept, document, error, isBlocked, isFeatureDisabled, isLoading, loadDocument, refresh, required],
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
