import React from "react";

interface BlockersPanelProps {
  blockers: string[];
  title?: string;
}

export const BlockersPanel: React.FC<BlockersPanelProps> = ({ blockers, title = "Blockers" }) => {
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {blockers.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {blockers.map((blocker) => (
            <span key={blocker} className="pill">
              {blocker}
            </span>
          ))}
        </div>
      ) : (
        <div className="muted">No blockers detected.</div>
      )}
    </div>
  );
};

export default BlockersPanel;
