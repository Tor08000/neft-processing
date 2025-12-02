import React, { createContext, useContext, useEffect, useState } from "react";
import { TOKEN_STORAGE_KEY } from "../api/client";

interface AuthContextValue {
  token: string | null;
  setToken: (token: string) => void;
  clearToken: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [token, setTokenState] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (stored) {
      setTokenState(stored);
    }
    setInitialized(true);
  }, []);

  const setToken = (value: string) => {
    localStorage.setItem(TOKEN_STORAGE_KEY, value);
    setTokenState(value);
  };

  const clearToken = () => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setTokenState(null);
  };

  if (!initialized) {
    return null;
  }

  return <AuthContext.Provider value={{ token, setToken, clearToken }}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
