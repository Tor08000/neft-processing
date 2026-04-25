import React from "react";

export const Loader: React.FC<{ label?: string }> = ({ label }) => (
  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
    <div
      style={{
        width: 16,
        height: 16,
        borderRadius: "50%",
        border: "2px solid #cbd5e1",
        borderTopColor: "#0ea5e9",
        animation: "spin 1s linear infinite",
      }}
    />
    <span>{label ?? "Loading..."}</span>
  </div>
);
