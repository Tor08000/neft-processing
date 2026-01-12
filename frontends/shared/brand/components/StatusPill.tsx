import type { ReactNode } from "react";

export type StatusTone = "success" | "warning" | "error" | "info" | "neutral";

export type StatusPillProps = {
  tone?: StatusTone;
  children: ReactNode;
};

const toneMap: Record<StatusTone, string> = {
  success: "ok",
  warning: "warn",
  error: "err",
  info: "info",
  neutral: "muted",
};

export function StatusPill({ tone = "neutral", children }: StatusPillProps) {
  const mapped = toneMap[tone];
  return <span className={`neft-chip neft-chip-${mapped}`}>{children}</span>;
}

export default StatusPill;
