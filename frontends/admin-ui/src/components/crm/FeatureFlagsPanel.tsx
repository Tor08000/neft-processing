import React from "react";

interface FeatureFlagsPanelProps {
  flags: Record<string, boolean>;
  onToggle: (feature: string, enabled: boolean) => void;
  disabled?: boolean;
}

const FEATURE_LABELS: Record<string, string> = {
  fuel: "Fuel",
  logistics: "Logistics",
  docs: "Docs",
  risk: "Risk",
};

export const FeatureFlagsPanel: React.FC<FeatureFlagsPanelProps> = ({ flags, onToggle, disabled }) => {
  const features = Object.keys(flags).length ? Object.keys(flags) : Object.keys(FEATURE_LABELS);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {features.map((feature) => {
        const enabled = Boolean(flags[feature]);
        return (
          <div key={feature} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 600 }}>{FEATURE_LABELS[feature] ?? feature}</div>
              <div style={{ color: "#64748b", fontSize: 12 }}>{feature}</div>
            </div>
            <button
              type="button"
              className="ghost"
              disabled={disabled}
              onClick={() => onToggle(feature, !enabled)}
            >
              {enabled ? "Disable" : "Enable"}
            </button>
          </div>
        );
      })}
    </div>
  );
};
