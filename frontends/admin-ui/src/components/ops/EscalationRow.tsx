import React from "react";

export type OpsEscalationRow = {
  id: string;
  target: string;
  status: string;
  priority: string;
  primary_reason: string;
  reason_code: string;
  subject_type: string;
  subject_id: string;
  sla_due_at: string | null;
  sla_overdue: boolean;
  created_at: string;
};

interface EscalationRowProps {
  item: OpsEscalationRow;
  isSelected: boolean;
  onSelect: (id: string) => void;
}

const formatCountdown = (dueAt?: string | null, overdue?: boolean) => {
  if (!dueAt) return "—";
  if (overdue) return "🔴 overdue";
  const due = new Date(dueAt);
  const diffMinutes = Math.max(0, Math.round((due.getTime() - Date.now()) / 60000));
  return `⏱ ${diffMinutes} мин`;
};

export const EscalationRow: React.FC<EscalationRowProps> = ({ item, isSelected, onSelect }) => {
  return (
    <tr
      onClick={() => onSelect(item.id)}
      style={{
        borderBottom: "1px solid #f1f5f9",
        background: isSelected ? "#f8fafc" : "transparent",
        cursor: "pointer",
      }}
    >
      <td style={{ padding: "8px 6px", fontSize: 12 }}>{new Date(item.created_at).toLocaleString()}</td>
      <td style={{ padding: "8px 6px" }}>{item.target}</td>
      <td style={{ padding: "8px 6px" }}>
        <span
          style={{
            padding: "4px 8px",
            borderRadius: 999,
            background: "#e2e8f0",
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {item.primary_reason}
        </span>
      </td>
      <td style={{ padding: "8px 6px", fontSize: 12, color: "#475569" }}>{item.reason_code}</td>
      <td style={{ padding: "8px 6px" }}>{formatCountdown(item.sla_due_at, item.sla_overdue)}</td>
      <td style={{ padding: "8px 6px" }}>{item.status}</td>
      <td style={{ padding: "8px 6px" }}>
        <div>{item.subject_type}</div>
        <div style={{ fontSize: 12, color: "#64748b" }}>{item.subject_id}</div>
      </td>
    </tr>
  );
};
