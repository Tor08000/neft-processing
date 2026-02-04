type Operation = {
  date: string;
  type: string;
  amount: number;
  status: "paid" | "pending" | "failed";
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value);

const statusLabels: Record<Operation["status"], string> = {
  paid: "Оплачено",
  pending: "Ожидает",
  failed: "Ошибка",
};

const statusClass: Record<Operation["status"], string> = {
  paid: "neftc-status-chip--success",
  pending: "neftc-status-chip--warning",
  failed: "neftc-status-chip--danger",
};

export function OperationRow({ operation }: { operation: Operation }) {
  return (
    <div className="neftc-operations__row">
      <div className="neftc-operations__date neftc-text-muted">{operation.date}</div>
      <div className="neftc-operations__type">{operation.type}</div>
      <div className="neftc-operations__amount">{formatCurrency(operation.amount)}</div>
      <span className={`neftc-status-chip ${statusClass[operation.status]}`}>{statusLabels[operation.status]}</span>
    </div>
  );
}
