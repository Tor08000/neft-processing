import React, { useEffect, useState } from "react";
import {
  adminLogin,
  getAdminOperations,
  getAdminTransactions,
  AdminOperation,
  AdminTransaction,
} from "./api/client";
import { useAuth } from "./store/auth";

type View = "operations" | "transactions";

const App: React.FC = () => {
  const { token, isAuthorized, login, logout } = useAuth();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("Admin123!");
  const [view, setView] = useState<View>("operations");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [operations, setOperations] = useState<AdminOperation[]>([]);
  const [transactions, setTransactions] = useState<AdminTransaction[]>([]);

  const [opsClientId, setOpsClientId] = useState("CLIENT-123");
  const [opsType, setOpsType] = useState<string>("");
  const [txClientId, setTxClientId] = useState("CLIENT-123");

  const [limit] = useState(10);
  const [offset] = useState(0);

  useEffect(() => {
    if (!token) return;
    if (view === "operations") {
      loadOperations(token);
    } else {
      loadTransactions(token);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, view]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const resp = await adminLogin({ email, password });
      login(resp.access_token);
    } catch (err: any) {
      setError(err.message || "Login error");
    } finally {
      setLoading(false);
    }
  }

  async function loadOperations(currentToken: string) {
    setLoading(true);
    setError(null);
    try {
      const resp = await getAdminOperations({
        token: currentToken,
        limit,
        offset,
        operation_type: opsType || undefined,
        client_id: opsClientId || undefined,
      });
      setOperations(resp.items);
    } catch (err: any) {
      setError(err.message || "Error loading operations");
    } finally {
      setLoading(false);
    }
  }

  async function loadTransactions(currentToken: string) {
    setLoading(true);
    setError(null);
    try {
      const resp = await getAdminTransactions({
        token: currentToken,
        limit,
        offset,
        client_id: txClientId || undefined,
      });
      setTransactions(resp.items);
    } catch (err: any) {
      setError(err.message || "Error loading transactions");
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    logout();
    setOperations([]);
    setTransactions([]);
  }

  if (!isAuthorized) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <h1>NEFT Admin Login</h1>
          <form onSubmit={handleLogin} style={styles.form}>
            <label style={styles.label}>
              Email
              <input
                style={styles.input}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label style={styles.label}>
              Password
              <input
                style={styles.input}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {error && <div style={styles.error}>{error}</div>}
            <button style={styles.button} type="submit" disabled={loading}>
              {loading ? "Вход..." : "Войти"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.appContainer}>
      <header style={styles.header}>
        <div>
          <strong>NEFT Admin Panel</strong>
        </div>
        <div>
          <button style={styles.tabButton} onClick={() => setView("operations")}>
            Операции
          </button>
          <button style={styles.tabButton} onClick={() => setView("transactions")}>
            Транзакции
          </button>
          <button style={styles.logoutButton} onClick={handleLogout}>
            Выйти
          </button>
        </div>
      </header>

      <main style={styles.main}>
        {error && <div style={styles.error}>{error}</div>}
        {view === "operations" && (
          <section>
            <h2>Операции</h2>
            <div style={styles.filters}>
              <div>
                <label>
                  client_id:
                  <input
                    style={styles.inputInline}
                    value={opsClientId}
                    onChange={(e) => setOpsClientId(e.target.value)}
                    placeholder="CLIENT-123"
                  />
                </label>
              </div>
              <div>
                <label>
                  operation_type:
                  <input
                    style={styles.inputInline}
                    value={opsType}
                    onChange={(e) => setOpsType(e.target.value)}
                    placeholder="REFUND / AUTH / CAPTURE..."
                  />
                </label>
              </div>
              <button
                style={styles.buttonSmall}
                onClick={() => token && loadOperations(token)}
                disabled={loading}
              >
                Обновить
              </button>
            </div>

            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.tableCell}>created_at</th>
                  <th style={styles.tableCell}>operation_id</th>
                  <th style={styles.tableCell}>type</th>
                  <th style={styles.tableCell}>status</th>
                  <th style={styles.tableCell}>client_id</th>
                  <th style={styles.tableCell}>card_id</th>
                  <th style={styles.tableCell}>merchant_id</th>
                  <th style={styles.tableCell}>terminal_id</th>
                  <th style={styles.tableCell}>amount</th>
                  <th style={styles.tableCell}>currency</th>
                </tr>
              </thead>
              <tbody>
                {operations.map((op) => (
                  <tr key={op.operation_id}>
                    <td style={styles.tableCell}>{op.created_at}</td>
                    <td style={styles.tableCell}>{op.operation_id}</td>
                    <td style={styles.tableCell}>{op.operation_type}</td>
                    <td style={styles.tableCell}>{op.status}</td>
                    <td style={styles.tableCell}>{op.client_id}</td>
                    <td style={styles.tableCell}>{op.card_id}</td>
                    <td style={styles.tableCell}>{op.merchant_id}</td>
                    <td style={styles.tableCell}>{op.terminal_id}</td>
                    <td style={styles.tableCell}>{op.amount}</td>
                    <td style={styles.tableCell}>{op.currency}</td>
                  </tr>
                ))}
                {operations.length === 0 && !loading && (
                  <tr>
                    <td colSpan={10} style={{ textAlign: "center", padding: "1rem" }}>
                      Нет данных
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>
        )}

        {view === "transactions" && (
          <section>
            <h2>Транзакции</h2>
            <div style={styles.filters}>
              <div>
                <label>
                  client_id:
                  <input
                    style={styles.inputInline}
                    value={txClientId}
                    onChange={(e) => setTxClientId(e.target.value)}
                    placeholder="CLIENT-123"
                  />
                </label>
              </div>
              <button
                style={styles.buttonSmall}
                onClick={() => token && loadTransactions(token)}
                disabled={loading}
              >
                Обновить
              </button>
            </div>

            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.tableCell}>created_at</th>
                  <th style={styles.tableCell}>transaction_id</th>
                  <th style={styles.tableCell}>status</th>
                  <th style={styles.tableCell}>client_id</th>
                  <th style={styles.tableCell}>card_id</th>
                  <th style={styles.tableCell}>merchant_id</th>
                  <th style={styles.tableCell}>terminal_id</th>
                  <th style={styles.tableCell}>authorized</th>
                  <th style={styles.tableCell}>captured</th>
                  <th style={styles.tableCell}>refunded</th>
                  <th style={styles.tableCell}>currency</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.transaction_id}>
                    <td style={styles.tableCell}>{tx.created_at}</td>
                    <td style={styles.tableCell}>{tx.transaction_id}</td>
                    <td style={styles.tableCell}>{tx.status}</td>
                    <td style={styles.tableCell}>{tx.client_id}</td>
                    <td style={styles.tableCell}>{tx.card_id}</td>
                    <td style={styles.tableCell}>{tx.merchant_id}</td>
                    <td style={styles.tableCell}>{tx.terminal_id}</td>
                    <td style={styles.tableCell}>{tx.authorized_amount}</td>
                    <td style={styles.tableCell}>{tx.captured_amount}</td>
                    <td style={styles.tableCell}>{tx.refunded_amount}</td>
                    <td style={styles.tableCell}>{tx.currency}</td>
                  </tr>
                ))}
                {transactions.length === 0 && !loading && (
                  <tr>
                    <td colSpan={11} style={{ textAlign: "center", padding: "1rem" }}>
                      Нет данных
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>
        )}
      </main>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#0f172a",
    color: "#e5e7eb",
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
  },
  card: {
    background: "#020617",
    padding: "2rem",
    borderRadius: "1rem",
    boxShadow: "0 20px 40px rgba(0,0,0,0.4)",
    minWidth: "320px",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
    marginTop: "1rem",
  },
  label: {
    display: "flex",
    flexDirection: "column",
    gap: "0.25rem",
    fontSize: "0.9rem",
  },
  input: {
    padding: "0.5rem 0.75rem",
    borderRadius: "0.5rem",
    border: "1px solid #334155",
    background: "#020617",
    color: "#e5e7eb",
  },
  inputInline: {
    padding: "0.25rem 0.5rem",
    borderRadius: "0.5rem",
    border: "1px solid #cbd5f5",
    marginLeft: "0.5rem",
  },
  button: {
    padding: "0.5rem 0.75rem",
    borderRadius: "0.5rem",
    border: "none",
    background: "#22c55e",
    color: "#022c22",
    fontWeight: 600,
    cursor: "pointer",
  },
  buttonSmall: {
    padding: "0.35rem 0.7rem",
    borderRadius: "0.5rem",
    border: "none",
    background: "#3b82f6",
    color: "#eff6ff",
    fontWeight: 500,
    cursor: "pointer",
  },
  error: {
    background: "#7f1d1d",
    color: "#fecaca",
    padding: "0.5rem 0.75rem",
    borderRadius: "0.5rem",
    fontSize: "0.85rem",
  },
  appContainer: {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    background: "#020617",
    color: "#e5e7eb",
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
  },
  header: {
    padding: "0.75rem 1.25rem",
    borderBottom: "1px solid #1e293b",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    background:
      "linear-gradient(to right, rgba(15,23,42,0.95), rgba(30,64,175,0.95))",
  },
  tabButton: {
    marginRight: "0.5rem",
    padding: "0.35rem 0.8rem",
    borderRadius: "999px",
    border: "1px solid #1d4ed8",
    background: "transparent",
    color: "#e5e7eb",
    cursor: "pointer",
    fontSize: "0.85rem",
  },
  logoutButton: {
    padding: "0.35rem 0.8rem",
    borderRadius: "999px",
    border: "1px solid #b91c1c",
    background: "transparent",
    color: "#fecaca",
    cursor: "pointer",
    fontSize: "0.85rem",
  },
  main: {
    padding: "1rem 1.25rem",
  },
  filters: {
    display: "flex",
    gap: "1rem",
    alignItems: "center",
    marginBottom: "0.75rem",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "0.8rem",
    background: "#020617",
    border: "1px solid #1e293b",
  },
  tableCell: {
    border: "1px solid #1e293b",
    padding: "0.35rem 0.5rem",
  },
};

export default App;
