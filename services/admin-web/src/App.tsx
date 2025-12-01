// services/admin-web/src/App.tsx

import React, { useEffect, useState } from "react";
import {
  adminLogin,
  getAdminOperations,
  getAdminTransactions,
  AdminOperation,
  AdminTransaction,
} from "./api/client";

type View = "operations" | "transactions";

const App: React.FC = () => {
  // Логин-форма
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("Admin123!");

  // Токен администратора
  const [token, setToken] = useState<string | null>(() =>
    typeof window !== "undefined" ? localStorage.getItem("admin_token") : null
  );

  // Основное состояние UI
  const [view, setView] = useState<View>("operations");
  const [operations, setOperations] = useState<AdminOperation[]>([]);
  const [transactions, setTransactions] = useState<AdminTransaction[]>([]);

  // Фильтры и пагинация
  const [limit, setLimit] = useState<number>(10);
  const [offset, setOffset] = useState<number>(0);
  const [clientId, setClientId] = useState<string>("CLIENT-123");
  const [operationType, setOperationType] = useState<string>("");

  // Служебные флаги
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Подгрузка данных при смене токена/вида/фильтров
  useEffect(() => {
    if (!token) return;

    setLoading(true);
    setError(null);

    const run = async () => {
      try {
        if (view === "operations") {
          const data = await getAdminOperations({
            token,
            limit,
            offset,
            operation_type: operationType || undefined,
            client_id: clientId || undefined,
          });
          setOperations(data.items);
        } else {
          const data = await getAdminTransactions({
            token,
            limit,
            offset,
            client_id: clientId || undefined,
          });
          setTransactions(data.items);
        }
      } catch (err: any) {
        console.error(err);
        setError(err?.message ?? "Ошибка при загрузке данных");
      } finally {
        setLoading(false);
      }
    };

    void run();
  }, [token, view, limit, offset, clientId, operationType]);

  // Обработчик логина
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await adminLogin(email, password);
      const newToken = res.access_token;

      setToken(newToken);
      if (typeof window !== "undefined") {
        localStorage.setItem("admin_token", newToken);
      }
    } catch (err: any) {
      console.error(err);
      setError(err?.message ?? "Ошибка авторизации");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("admin_token");
    }
    setOperations([]);
    setTransactions([]);
  };

  const isAuthenticated = Boolean(token);

  // =========================
  // Рендер
  // =========================

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#0b1220",
        color: "#e5e7eb",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      <div
        style={{
          width: "480px",
          maxWidth: "100%",
          backgroundColor: "#020617",
          borderRadius: "1rem",
          padding: "2rem",
          boxShadow: "0 25px 50px -12px rgba(15,23,42,0.8)",
        }}
      >
        <h1
          style={{
            fontSize: "1.75rem",
            fontWeight: 700,
            marginBottom: "1.5rem",
            textAlign: "center",
          }}
        >
          NEFT Admin Login
        </h1>

        {/* Форма логина */}
        <form onSubmit={handleLogin} style={{ marginBottom: "1.5rem" }}>
          <div style={{ marginBottom: "0.75rem" }}>
            <label
              style={{
                display: "block",
                fontSize: "0.875rem",
                marginBottom: "0.25rem",
              }}
            >
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{
                width: "100%",
                padding: "0.5rem 0.75rem",
                borderRadius: "0.5rem",
                border: "1px solid #1f2937",
                backgroundColor: "#020617",
                color: "#e5e7eb",
                outline: "none",
              }}
            />
          </div>

          <div style={{ marginBottom: "0.75rem" }}>
            <label
              style={{
                display: "block",
                fontSize: "0.875rem",
                marginBottom: "0.25rem",
              }}
            >
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                width: "100%",
                padding: "0.5rem 0.75rem",
                borderRadius: "0.5rem",
                border: "1px solid #1f2937",
                backgroundColor: "#020617",
                color: "#e5e7eb",
                outline: "none",
              }}
            />
          </div>

          {error && (
            <div
              style={{
                backgroundColor: "#7f1d1d",
                color: "#fee2e2",
                borderRadius: "0.5rem",
                padding: "0.5rem 0.75rem",
                fontSize: "0.875rem",
                marginBottom: "0.75rem",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "0.75rem",
              borderRadius: "0.75rem",
              border: "none",
              cursor: "pointer",
              fontWeight: 600,
              backgroundColor: "#22c55e",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? "Входим..." : "Войти"}
          </button>
        </form>

        {/* Если залогинен — показываем фильтры и табы */}
        {isAuthenticated && (
          <>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: "0.75rem",
                gap: "0.5rem",
              }}
            >
              <button
                type="button"
                onClick={() => setView("operations")}
                style={{
                  flex: 1,
                  padding: "0.5rem",
                  borderRadius: "0.5rem",
                  border: "none",
                  cursor: "pointer",
                  backgroundColor:
                    view === "operations" ? "#1d4ed8" : "#111827",
                  color: "#e5e7eb",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                }}
              >
                Операции
              </button>
              <button
                type="button"
                onClick={() => setView("transactions")}
                style={{
                  flex: 1,
                  padding: "0.5rem",
                  borderRadius: "0.5rem",
                  border: "none",
                  cursor: "pointer",
                  backgroundColor:
                    view === "transactions" ? "#1d4ed8" : "#111827",
                  color: "#e5e7eb",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                }}
              >
                Транзакции
              </button>
              <button
                type="button"
                onClick={handleLogout}
                style={{
                  padding: "0.5rem 0.75rem",
                  borderRadius: "0.5rem",
                  border: "none",
                  cursor: "pointer",
                  backgroundColor: "#b91c1c",
                  color: "#fee2e2",
                  fontSize: "0.75rem",
                  whiteSpace: "nowrap",
                }}
              >
                Выйти
              </button>
            </div>

            {/* Фильтры */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.5rem",
                marginBottom: "0.75rem",
                fontSize: "0.75rem",
              }}
            >
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <div style={{ flex: 1 }}>
                  <label>Client ID</label>
                  <input
                    value={clientId}
                    onChange={(e) => setClientId(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "0.25rem 0.5rem",
                      borderRadius: "0.5rem",
                      border: "1px solid #1f2937",
                      backgroundColor: "#020617",
                      color: "#e5e7eb",
                    }}
                  />
                </div>
                {view === "operations" && (
                  <div style={{ flex: 1 }}>
                    <label>Operation type</label>
                    <input
                      value={operationType}
                      onChange={(e) => setOperationType(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "0.25rem 0.5rem",
                        borderRadius: "0.5rem",
                        border: "1px solid #1f2937",
                        backgroundColor: "#020617",
                        color: "#e5e7eb",
                      }}
                    />
                  </div>
                )}
              </div>

              <div style={{ display: "flex", gap: "0.5rem" }}>
                <div>
                  <label>Limit</label>
                  <input
                    type="number"
                    min={1}
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value) || 10)}
                    style={{
                      width: "4rem",
                      padding: "0.25rem 0.5rem",
                      borderRadius: "0.5rem",
                      border: "1px solid #1f2937",
                      backgroundColor: "#020617",
                      color: "#e5e7eb",
                    }}
                  />
                </div>
                <div>
                  <label>Offset</label>
                  <input
                    type="number"
                    min={0}
                    value={offset}
                    onChange={(e) => setOffset(Number(e.target.value) || 0)}
                    style={{
                      width: "4rem",
                      padding: "0.25rem 0.5rem",
                      borderRadius: "0.5rem",
                      border: "1px solid #1f2937",
                      backgroundColor: "#020617",
                      color: "#e5e7eb",
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Таблица */}
            <div
              style={{
                maxHeight: "260px",
                overflow: "auto",
                borderRadius: "0.75rem",
                border: "1px solid #1f2937",
              }}
            >
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "0.75rem",
                }}
              >
                <thead style={{ backgroundColor: "#020617" }}>
                  <tr>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "0.5rem",
                        borderBottom: "1px solid #1f2937",
                      }}
                    >
                      ID
                    </th>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "0.5rem",
                        borderBottom: "1px solid #1f2937",
                      }}
                    >
                      Status
                    </th>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "0.5rem",
                        borderBottom: "1px solid #1f2937",
                      }}
                    >
                      Amount
                    </th>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "0.5rem",
                        borderBottom: "1px solid #1f2937",
                      }}
                    >
                      Client
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {view === "operations"
                    ? operations.map((op) => (
                        <tr key={op.operation_id}>
                          <td
                            style={{
                              padding: "0.5rem",
                              borderBottom: "1px solid #111827",
                            }}
                          >
                            {op.operation_id}
                          </td>
                          <td
                            style={{
                              padding: "0.5rem",
                              borderBottom: "1px solid #111827",
                            }}
                          >
                            {op.status} / {op.operation_type}
                          </td>
                          <td
                            style={{
                              padding: "0.5rem",
                              borderBottom: "1px solid #111827",
                            }}
                          >
                            {op.amount} {op.currency}
                          </td>
                          <td
                            style={{
                              padding: "0.5rem",
                              borderBottom: "1px solid #111827",
                            }}
                          >
                            {op.client_id}
                          </td>
                        </tr>
                      ))
                    : transactions.map((tx) => (
                        <tr key={tx.transaction_id}>
                          <td
                            style={{
                              padding: "0.5rem",
                              borderBottom: "1px solid #111827",
                            }}
                          >
                            {tx.transaction_id}
                          </td>
                          <td
                            style={{
                              padding: "0.5rem",
                              borderBottom: "1px solid #111827",
                            }}
                          >
                            {tx.status}
                          </td>
                          <td
                            style={{
                              padding: "0.5rem",
                              borderBottom: "1px solid #111827",
                            }}
                          >
                            {tx.captured_amount || tx.authorized_amount}{" "}
                            {tx.currency}
                          </td>
                          <td
                            style={{
                              padding: "0.5rem",
                              borderBottom: "1px solid #111827",
                            }}
                          >
                            {tx.client_id}
                          </td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default App;
