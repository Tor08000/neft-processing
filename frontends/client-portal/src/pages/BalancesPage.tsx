import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { fetchBalances } from "../api/balances";
import { fetchStatements } from "../api/statements";
import { useAuth } from "../auth/AuthContext";
import type { BalanceItem } from "../types/balances";
import type { Statement } from "../types/statements";
import { MoneyValue } from "../components/common/MoneyValue";
import { Table, type Column } from "../components/common/Table";
import { FinanceOverview } from "@shared/brand/components";

const todayIso = () => new Date().toISOString().slice(0, 10);

export function BalancesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<BalanceItem[]>([]);
  const [statements, setStatements] = useState<Statement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState(() => {
    const to = todayIso();
    const fromDate = new Date();
    fromDate.setDate(fromDate.getDate() - 30);
    const from = fromDate.toISOString().slice(0, 10);
    return { from, to };
  });

  const loadBalances = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchBalances(user),
      fetchStatements(user, { from: filters.from, to: filters.to }),
    ])
      .then(([balancesResp, statementsResp]) => {
        setItems(balancesResp.items ?? []);
        setStatements(statementsResp);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [filters.from, filters.to, user]);

  useEffect(() => {
    loadBalances();
  }, [loadBalances]);

  const totals = useMemo(() => {
    const totalCurrent = items.reduce((acc, item) => acc + Number(item.current ?? 0), 0);
    const totalTopup = statements.reduce((acc, s) => acc + Number(s.credits ?? 0), 0);
    const totalSpent = statements.reduce((acc, s) => acc + Number(s.debits ?? 0), 0);
    return { totalCurrent, totalTopup, totalSpent };
  }, [items, statements]);

  const handleFilterChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  if (!user) {
    return null;
  }

  const columns = useMemo<Column<BalanceItem>[]>(
    () => [
      { key: "currency", title: "Валюта", dataIndex: "currency" },
      {
        key: "current",
        title: "Текущий баланс",
        className: "neft-num",
        render: (item) => <MoneyValue amount={item.current} currency={item.currency} />,
      },
      {
        key: "available",
        title: "Доступно",
        className: "neft-num",
        render: (item) => <MoneyValue amount={item.available} currency={item.currency} />,
      },
    ],
    [],
  );

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h1>Балансы и доступные средства</h1>
          <p className="muted">Актуальные остатки и движение средств за период</p>
        </div>
      </div>

      <section className="card">
        <FinanceOverview
          items={[
            {
              id: "current",
              label: "Текущий баланс",
              value: <MoneyValue amount={totals.totalCurrent} currency={items[0]?.currency ?? "RUB"} />,
              tone: "info",
            },
            {
              id: "topup",
              label: "Пополнено за период",
              value: <MoneyValue amount={totals.totalTopup} currency={items[0]?.currency ?? "RUB"} />,
              tone: "success",
            },
            {
              id: "spent",
              label: "Израсходовано за период",
              value: <MoneyValue amount={totals.totalSpent} currency={items[0]?.currency ?? "RUB"} />,
              tone: "warning",
            },
          ]}
        />

        <Table
          columns={columns}
          data={items}
          loading={loading}
          rowKey={(item) => item.currency}
          toolbar={
            <div className="filters">
              <div className="filter">
                <label htmlFor="balances-from">Период с</label>
                <input
                  id="balances-from"
                  name="from"
                  type="date"
                  value={filters.from}
                  onChange={handleFilterChange}
                />
              </div>
              <div className="filter">
                <label htmlFor="balances-to">Период по</label>
                <input id="balances-to" name="to" type="date" value={filters.to} onChange={handleFilterChange} />
              </div>
            </div>
          }
          errorState={
            error
              ? {
                  title: "Не удалось загрузить балансы",
                  description: error,
                  actionLabel: "Повторить",
                  actionOnClick: loadBalances,
                }
              : undefined
          }
          emptyState={{
            title: "Балансовые счета пока недоступны",
            description: "Финансовый контур откроет здесь остатки и обороты после активации счёта организации.",
            hint: `Период отчёта: ${filters.from} — ${filters.to}`,
            actionLabel: "Обновить",
            actionOnClick: loadBalances,
          }}
          footer={
            error ? null : (
              <div className="table-footer__content muted">
                <span>Счетов: {items.length}</span>
                <span>Проводок за период: {statements.length}</span>
              </div>
            )
          }
        />
      </section>
    </div>
  );
}
