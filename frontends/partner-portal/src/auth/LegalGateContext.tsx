import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { acceptLegalDocument, fetchLegalDocument, fetchLegalRequired } from "../api/legal";
import type { LegalDocumentResponse, LegalRequiredItem, LegalRequiredResponse } from "../api/legal";
import { useAuth } from "./AuthContext";

const CACHE_TTL_MS = 60_000;

interface LegalGateContextValue {
  required: LegalRequiredItem[];
  isBlocked: boolean;
  isLoading: boolean;
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
  const [lastFetched, setLastFetched] = useState<number | null>(null);
  const [document, setDocument] = useState<LegalDocumentResponse | null>(null);

  const refresh = useCallback(
    async (force = false) => {
      if (!user?.token) return;
      const now = Date.now();
      if (!force && lastFetched && now - lastFetched < CACHE_TTL_MS) {
        return;
      }
      setIsLoading(true);
      try {
        const data = (await fetchLegalRequired(user.token)) as LegalRequiredResponse;
        setRequired(data.required ?? []);
        setIsBlocked(Boolean(data.is_blocked));
        setLastFetched(now);
      } finally {
        setIsLoading(false);
      }
    },
    [lastFetched, user?.token],
  );

  const accept = useCallback(
    async (code: string, version: string, locale: string) => {
      if (!user?.token) return;
      setIsLoading(true);
      try {
        const data = await acceptLegalDocument(user.token, { code, version, locale });
        setRequired(data.required ?? []);
        setIsBlocked(Boolean(data.is_blocked));
        setLastFetched(Date.now());
      } finally {
        setIsLoading(false);
      }
    },
    [user?.token],
  );

  const loadDocument = useCallback(
    async (code: string, version: string, locale: string) => {
      if (!user?.token) return;
      setIsLoading(true);
      try {
        const data = await fetchLegalDocument(user.token, code, { version, locale });
        setDocument(data);
      } finally {
        setIsLoading(false);
      }
    },
    [user?.token],
  );

  useEffect(() => {
    if (user?.token) {
      void refresh(true);
    }
  }, [refresh, user?.token]);

  useEffect(() => {
    const handler = () => {
      void refresh(true);
      if (location.pathname !== "/legal") {
        navigate("/legal", { replace: true });
      }
    };
    window.addEventListener("legal-required", handler);
    return () => window.removeEventListener("legal-required", handler);
  }, [location.pathname, navigate, refresh]);

  const value = useMemo(
    () => ({
      required,
      isBlocked,
      isLoading,
      document,
      loadDocument,
      refresh,
      accept,
    }),
    [accept, document, isBlocked, isLoading, loadDocument, refresh, required],
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
