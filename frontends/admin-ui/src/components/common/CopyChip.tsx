import React, { useEffect, useState } from "react";

interface CopyChipProps {
  label: string;
  value: string;
  onCopy?: () => void;
}

export const CopyChip: React.FC<CopyChipProps> = ({ label, value, onCopy }) => {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      onCopy?.();
    } catch (err) {
      console.error("Copy failed", err);
    }
  };

  return (
    <div className="copy-chip">
      <span className="copy-chip__label">{label}</span>
      <span className="copy-chip__value" title={value}>
        {value}
      </span>
      <button type="button" className="copy-chip__button neft-btn-outline neft-focus-ring" onClick={handleCopy}>
        {copied ? "Скопировано" : "Копировать"}
      </button>
    </div>
  );
};
