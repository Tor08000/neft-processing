import { useMemo, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardPage } from "./pages/DashboardPage";
import { LimitsPage } from "./pages/LimitsPage";
import { LoginPage } from "./pages/LoginPage";
import { OperationsPage } from "./pages/OperationsPage";
import { Layout } from "./components/Layout";
import type { ClientUser, DashboardSummary, Limit, Operation } from "./types";

const queryClient = new QueryClient();

const demoUser: ClientUser = {
  id: "demo-user",
  email: "demo@client.neft",
  fullName: "Demo Client",
  role: "OWNER",
  status: "active",
  organization: {
    id: "org-001",
    name: "Demo Logistics LLC",
    inn: "1234567890",
    status: "active",
  },
};

const demoOperations: Operation[] = [
  {
    id: "op-1",
    date: new Date().toISOString(),
    type: "auth",
    status: "success",
    amount: 18000,
    fuelType: "diesel",
    cardRef: "**** 1234",
  },
  {
    id: "op-2",
    date: new Date(Date.now() - 3_600_000).toISOString(),
    type: "capture",
    status: "pending",
    amount: 7200,
    fuelType: "gasoline",
    cardRef: "**** 9876",
  },
  {
    id: "op-3",
    date: new Date(Date.now() - 48 * 3_600_000).toISOString(),
    type: "refund",
    status: "failed",
    amount: 1500,
    fuelType: "diesel",
    cardRef: "**** 5555",
  },
];

const demoLimits: Limit[] = [
  { id: "limit-1", type: "Суточный", period: "day", amount: 50000, used: 18000 },
  { id: "limit-2", type: "Недельный", period: "week", amount: 250000, used: 62000 },
  { id: "limit-3", type: "Месячный", period: "month", amount: 1000000, used: 240000 },
];

const dashboardSummary: DashboardSummary = {
  totalOperations: demoOperations.length,
  totalAmount: demoOperations.reduce((acc, op) => acc + op.amount, 0),
  period: "7 дней",
  activeLimits: demoLimits.length,
};

function AppRoutes() {
  const [user, setUser] = useState<ClientUser | null>(null);
  const navigate = useNavigate();

  const handleLogin = (email: string, password: string) => {
    if (!email || !password) {
      return;
    }
    // Здесь будет вызов /client/api/v1/auth/login. Пока — демо-ответ
    setUser({ ...demoUser, email });
    navigate("/dashboard");
  };

  const lastOperations = useMemo(() => demoOperations.slice(0, 5), []);

  if (!user) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <Layout user={user}>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" />} />
        <Route
          path="/dashboard"
          element={<DashboardPage summary={dashboardSummary} lastOperations={lastOperations} />}
        />
        <Route path="/operations" element={<OperationsPage operations={demoOperations} />} />
        <Route path="/limits" element={<LimitsPage limits={demoLimits} />} />
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
