import React, { createContext, useContext, useEffect, useState } from "react";

interface AuthContextValue {
  token: string | null;
  isAuthorized: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const saved = window.localStorage.getItem("neft_admin_token");
    if (saved) setToken(saved);
  }, []);

  const login = (newToken: string) => {
    setToken(newToken);
    window.localStorage.setItem("neft_admin_token", newToken);
  };

  const logout = () => {
    setToken(null);
    window.localStorage.removeItem("neft_admin_token");
  };

  return (
    <AuthContext.Provider value={{ token, isAuthorized: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
