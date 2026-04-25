import React from "react";

interface FeatureFlagsPanelProps {
  flags: Record<string, boolean>;
  onToggle: (feature: string, enabled: boolean) => void;
  disabled?: boolean;
}

const FEATURE_LABELS: Record<string, string> = {
  FUEL_ENABLED: "Fuel access",
  LOGISTICS_ENABLED: "Logistics access",
  DOCUMENTS_ENABLED: "Documents access",
  RISK_BLOCKING_ENABLED: "Risk blocking",
  ACCOUNTING_EXPORT_ENABLED: "Accounting export",
  SUBSCRIPTION_METER_FUEL_ENABLED: "Subscription fuel metering",
  CASES_ENABLED: "Cases integration",
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
