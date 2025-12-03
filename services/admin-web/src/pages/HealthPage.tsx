import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "../api/health";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { ServiceHealth } from "../types/health";
import { Loader } from "../components/Loader/Loader";

export const HealthPage: React.FC = () => {
  const { data = [], isFetching, isLoading, error, refetch } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  return (
    <div>
      <div className="page-header">
        <h1>Health</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => refetch()} disabled={isFetching}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Проверяем сервисы" />}
          {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
        </div>
      </div>

      <div className="status-grid">
        {data.map((item) => (
          <div key={item.service} className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>{item.service}</strong>
              <StatusBadge status={item.status.toUpperCase()} />
            </div>
            {item.details && (
              <pre style={{ background: "#f8fafc", padding: 8, borderRadius: 8, overflow: "auto" }}>
                {JSON.stringify(item.details, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {data.length === 0 && !isLoading && <p>No health data</p>}
      </div>
    </div>
  );
};

export default HealthPage;
