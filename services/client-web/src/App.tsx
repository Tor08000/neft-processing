import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { DashboardPage } from "./pages/DashboardPage";
import { LimitsPage } from "./pages/LimitsPage";
import { LoginPage } from "./pages/LoginPage";
import { OperationsPage } from "./pages/OperationsPage";
import { Layout } from "./components/Layout";
import type { ClientUser } from "./types";
import { fetchDashboard, fetchLimits, fetchMe, fetchOperations, login } from "./api";

const queryClient = new QueryClient();

function AppRoutes() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<ClientUser | undefined>(undefined);
  const navigate = useNavigate();

  useEffect(() => {
    const saved = localStorage.getItem("client_token");
    if (saved) {
      setToken(saved);
    }
  }, []);

  const { data: profile } = useQuery<ClientUser, Error, ClientUser, [string, string | null]>({
    queryKey: ["me", token],
    queryFn: ({ queryKey: [, authToken] }) => fetchMe(authToken ?? ""),
    enabled: Boolean(token),
  });

  useEffect(() => {
    if (profile) {
      setUser(profile);
    }
  }, [profile]);

  const handleLogin = async (email: string, password: string) => {
    const auth = await login(email, password);
    setToken(auth.token);
    localStorage.setItem("client_token", auth.token);
    const me = await fetchMe(auth.token);
    setUser(me);
    navigate("/dashboard");
  };

  if (!token) {
    return <LoginPage onLogin={handleLogin} />;
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
