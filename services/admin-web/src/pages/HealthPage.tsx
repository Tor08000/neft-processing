import React, { useEffect, useState } from "react";
import { fetchHealth } from "../api/health";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { ServiceHealth } from "../types/health";

export const HealthPage: React.FC = () => {
  const [data, setData] = useState<ServiceHealth[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchHealth();
      setData(res);
    } catch (err: any) {
      setError(err?.message ?? "Не удалось загрузить health");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>Health</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => load()} disabled={loading}>
            Refresh
          </button>
          {loading && <span>Loading...</span>}
          {error && <span style={{ color: "#dc2626" }}>{error}</span>}
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
        {data.length === 0 && !loading && <p>No health data</p>}
      </div>
    </div>
  );
};
