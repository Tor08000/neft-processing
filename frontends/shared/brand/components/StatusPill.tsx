import React from "react";

export type StatusTone = "success" | "warning" | "error" | "info" | "neutral";

export type StatusPillProps = {
  tone?: StatusTone;
  children: React.ReactNode;
};

export const StatusPill: React.FC<StatusPillProps> = ({ tone = "neutral", children }) => {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>;
};

export default StatusPill;
