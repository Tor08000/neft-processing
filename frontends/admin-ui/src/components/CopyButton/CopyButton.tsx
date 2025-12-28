import React, { useState } from "react";

interface CopyButtonProps {
  value?: string | null;
  label?: string;
  onCopy?: () => void;
}

export const CopyButton: React.FC<CopyButtonProps> = ({ value, label = "Copy", onCopy }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      onCopy?.();
      window.setTimeout(() => setCopied(false), 1200);
    } catch (err) {
      console.error("Failed to copy", err);
    }
  };

  return (
    <button type="button" className="ghost" onClick={handleCopy} disabled={!value}>
      {copied ? "Copied" : label}
    </button>
  );
};
