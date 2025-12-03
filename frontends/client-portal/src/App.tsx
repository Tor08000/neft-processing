import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { DashboardPage } from "./pages/DashboardPage";
import { LimitsPage } from "./pages/LimitsPage";
import { LoginPage } from "./pages/LoginPage";
import { OperationsPage } from "./pages/OperationsPage";
import { Layout } from "./components/Layout";
import type { ClientUser } from "./types";
import {
  UnauthorizedError,
  InvalidLoginPayloadError,
  fetchDashboard,
  fetchLimits,
  fetchMe,
  fetchOperations,
  login,
} from "./api";

const queryClient = new QueryClient();

function AppRoutes() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<ClientUser | undefined>(undefined);
  const [loginError, setLoginError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const saved = localStorage.getItem("client_token");
    if (saved) {
      setToken(saved);
    }
  }, []);

  const {
    data: profile,
    error: profileError,
    isError: isProfileError,
    isSuccess: isProfileSuccess,
  } = useQuery<ClientUser, Error, ClientUser, [string, string | null]>({
    queryKey: ["me", token],
    queryFn: ({ queryKey: [, authToken] }) => fetchMe(authToken ?? ""),
    enabled: Boolean(token),
    retry: false,
  });

  useEffect(() => {
    if (isProfileSuccess && profile) {
      setUser(profile);
    }
  }, [isProfileSuccess, profile]);

  useEffect(() => {
    if (isProfileError && profileError instanceof UnauthorizedError) {
      localStorage.removeItem("client_token");
      setToken(null);
      setUser(undefined);
      navigate("/login", { replace: true });
    }
  }, [isProfileError, profileError, navigate]);

  const handleLogin = async (email: string, password: string) => {
    try {
      const auth = await login(email, password);
      setToken(auth.token);
      localStorage.setItem("client_token", auth.token);
      const me = await fetchMe(auth.token);
      setUser(me);
      setLoginError(null);
      navigate("/dashboard");
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        setLoginError("Неверный email или пароль демо-клиента");
        return;
      }
      if (error instanceof InvalidLoginPayloadError) {
        console.error("Получена ошибка валидации при входе", error);
        setLoginError("Не удалось выполнить вход. Попробуйте ещё раз.");
        return;
      }
      setLoginError("Не удалось выполнить вход. Попробуйте ещё раз.");
    }
  };

  if (!token) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage onLogin={handleLogin} error={loginError ?? undefined} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Layout user={profile ?? user}>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" />} />
        <Route path="/dashboard" element={<DashboardPage token={token} />} />
        <Route path="/operations" element={<OperationsPage token={token} />} />
        <Route path="/limits" element={<LimitsPage token={token} />} />
      </Routes>
    </Layout>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppRoutes />
    </QueryClientProvider>
  );
}
