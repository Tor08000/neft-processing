import React from "react";

export interface TabItem {
  id: string;
  label: string;
}

interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (id: string) => void;
}

export const Tabs: React.FC<TabsProps> = ({ tabs, active, onChange }) => {
  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className="ghost"
          onClick={() => onChange(tab.id)}
          style={{
            background: active === tab.id ? "#1e293b" : "#fff",
            color: active === tab.id ? "#fff" : "#1e293b",
            borderColor: active === tab.id ? "#1e293b" : "#cbd5e1",
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
};
