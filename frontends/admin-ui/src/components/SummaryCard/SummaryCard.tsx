import React from "react";

interface Props {
  title: string;
  value: React.ReactNode;
  description?: string;
}

export const SummaryCard: React.FC<Props> = ({ title, value, description }) => {
  return (
    <div className="card neft-card">
      <div style={{ fontSize: 14, color: "var(--neft-text-muted)", marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 24, fontWeight: 800, color: "var(--neft-text)" }}>{value}</div>
      {description && (
        <div style={{ marginTop: 6, color: "var(--neft-text-muted)", fontSize: 13 }}>{description}</div>
      )}
    </div>
  );
};
