import { useMemo, useState } from "react";
import { request } from "../api/http";
import { useAuth } from "../auth/AuthContext";

const VIEW_OPTIONS = ["FULL", "FLEET", "ACCOUNTANT"] as const;
const SUBJECT_OPTIONS = [
  { value: "fuel_tx_id", label: "Fuel transaction" },
  { value: "order_id", label: "Order" },
  { value: "invoice_id", label: "Invoice" },
] as const;

export const UnifiedExplainPage = () => {
  const { accessToken } = useAuth();
  const [subjectType, setSubjectType] = useState<(typeof SUBJECT_OPTIONS)[number]["value"]>("fuel_tx_id");
  const [subjectId, setSubjectId] = useState("");
  const [view, setView] = useState<(typeof VIEW_OPTIONS)[number]>("FULL");
  const [depth, setDepth] = useState(3);
  const [snapshot, setSnapshot] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);

  const canSubmit = subjectId.trim().length > 0;

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set(subjectType, subjectId.trim());
    params.set("view", view);
    params.set("depth", String(depth));
    if (snapshot) {
      params.set("snapshot", "true");
    }
    return params.toString();
  }, [subjectId, subjectType, view, depth, snapshot]);

  const handleSubmit = async (forceSnapshot = false) => {
    if (!canSubmit) {
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      const snapshotParam = forceSnapshot ? "true" : snapshot ? "true" : undefined;
      const params = new URLSearchParams(query);
      if (snapshotParam) {
        params.set("snapshot", snapshotParam);
      }
      const data = await request<Record<string, unknown>>(
        `/api/v1/admin/explain?${params.toString()}`,
        {},
        accessToken,
      );
      setPayload(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить explain");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Unified Explain</h1>
        <p style={{ color: "#475569" }}>
          Поиск причин отказа/рисков для fuel, order или invoice.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Subject type</span>
          <select value={subjectType} onChange={(event) => setSubjectType(event.target.value as typeof subjectType)}>
            {SUBJECT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>ID</span>
          <input
            type="text"
            value={subjectId}
            placeholder="Введите ID"
            onChange={(event) => setSubjectId(event.target.value)}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>View</span>
          <select value={view} onChange={(event) => setView(event.target.value as typeof view)}>
            {VIEW_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Depth</span>
          <input
            type="number"
            min={1}
            max={5}
            value={depth}
            onChange={(event) => setDepth(Number(event.target.value))}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 24 }}>
          <input type="checkbox" checked={snapshot} onChange={(event) => setSnapshot(event.target.checked)} />
          Создать snapshot
        </label>
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <button
          onClick={() => handleSubmit(false)}
          disabled={!canSubmit || isLoading}
          style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #cbd5e1" }}
        >
          {isLoading ? "Загрузка..." : "Получить объяснение"}
        </button>
        <button
          onClick={() => handleSubmit(true)}
          disabled={!canSubmit || isLoading}
          style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #cbd5e1" }}
        >
          Create snapshot
        </button>
      </div>

      {error ? (
        <div style={{ color: "#b91c1c", background: "#fee2e2", padding: 12, borderRadius: 8 }}>{error}</div>
      ) : null}

      <div style={{ background: "#0f172a", color: "#f8fafc", padding: 16, borderRadius: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Ответ</div>
        <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
          {payload ? JSON.stringify(payload, null, 2) : "Нет данных"}
        </pre>
      </div>
    </div>
  );
};

export default UnifiedExplainPage;
