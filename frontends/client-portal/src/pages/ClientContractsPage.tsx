import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchClientContracts } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import { Table } from "../components/common/Table";
import type { ClientContractSummary } from "../types/portal";
import { formatDate } from "../utils/format";

const slaTone = (status: string) => {
  if (status === "OK") return "ok";
  if (status === "VIOLATIONS") return "warn";
  return "muted";
};

export function ClientContractsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ClientContractSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchClientContracts(user)
      .then((data) => setItems(data.items ?? []))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [reloadNonce, user]);

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h2>Контракты</h2>
          <p className="muted">Сводка по действующим контрактам и SLA.</p>
        </div>
      </div>
      <Table
        columns={[
          {
            key: "contract_number",
            title: "Контракт",
            render: (contract) => contract.contract_number,
          },
          {
            key: "contract_type",
            title: "Тип",
            render: (contract) => contract.contract_type,
          },
          {
            key: "dates",
            title: "Даты",
            render: (contract) =>
              `${formatDate(contract.effective_from)} — ${contract.effective_to ? formatDate(contract.effective_to) : "—"}`,
          },
          {
            key: "sla_status",
            title: "SLA",
            render: (contract) => (
              <span className={`neft-chip neft-chip-${slaTone(contract.sla_status)}`}>{contract.sla_status}</span>
            ),
          },
          {
            key: "sla_violations",
            title: "Нарушения",
            render: (contract) => contract.sla_violations,
          },
          {
            key: "actions",
            title: "",
            render: (contract) => (
              <div className="table-row-actions">
                <Link className="ghost" to={`/contracts/${contract.contract_number}`}>
                  Открыть
                </Link>
              </div>
            ),
          },
        ]}
        data={items}
        loading={isLoading}
        rowKey={(contract) => contract.contract_number}
        errorState={
          error
            ? {
                title: "Не удалось загрузить контракты",
                description: error,
                actionLabel: "Повторить",
                actionOnClick: () => setReloadNonce((value) => value + 1),
              }
            : undefined
        }
        emptyState={{
          title: "Контрактов пока нет",
          description: "Когда появятся действующие клиентские контракты, они будут показаны здесь.",
        }}
        footer={<div className="table-footer__content muted">Контрактов: {items.length}</div>}
      />
    </div>
  );
}
