import React from "react";

interface Props {
  title: string;
  value: React.ReactNode;
  description?: string;
}

export const SummaryCard: React.FC<Props> = ({ title, value, description }) => {
  return (
    <div className="card">
      <div style={{ fontSize: 14, color: "#475569", marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a" }}>{value}</div>
      {description && <div style={{ marginTop: 6, color: "#475569", fontSize: 13 }}>{description}</div>}
    </div>
  );
};
