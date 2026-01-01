import { useCallback, useEffect, useState } from "react";

export type ToastKind = "success" | "error" | "info";

export type ToastMessage = {
  kind: ToastKind;
  text: string;
};

export function useToast() {
  const [toast, setToast] = useState<ToastMessage | null>(null);

  const showToast = useCallback((kind: ToastKind, text: string) => {
    setToast({ kind, text });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  return { toast, showToast };
}
