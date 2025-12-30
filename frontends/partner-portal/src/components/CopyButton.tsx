import { useEffect, useState } from "react";

interface CopyButtonProps {
  value: string | null | undefined;
  label?: string;
}

export function CopyButton({ value, label = "Скопировать" }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  if (!value) {
    return null;
  }

  const handleClick = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch (err) {
      setCopied(false);
    }
  };

  return (
    <button type="button" className="copy-button" onClick={handleClick} aria-live="polite">
      {copied ? "Скопировано" : label}
    </button>
  );
}
