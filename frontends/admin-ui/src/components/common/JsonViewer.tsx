import React, { useMemo } from "react";
import { CopyButton } from "../CopyButton/CopyButton";

interface JsonViewerProps {
  value: unknown;
  title?: string;
}

export const JsonViewer: React.FC<JsonViewerProps> = ({ value, title }) => {
  const formatted = useMemo(() => {
    if (typeof value === "string") {
      try {
        return JSON.stringify(JSON.parse(value), null, 2);
      } catch {
        return value;
      }
    }
    return JSON.stringify(value ?? {}, null, 2);
  }, [value]);

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 12, background: "#f8fafc" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <strong>{title ?? "JSON"}</strong>
        <CopyButton value={formatted} label="Copy JSON" />
      </div>
      <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>{formatted}</pre>
    </div>
  );
};
