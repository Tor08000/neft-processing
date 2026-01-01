import type { ToastMessage } from "./useToast";

export function Toast({ toast }: { toast: ToastMessage | null }) {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.kind}`} role="status" aria-live="polite">
      <span>{toast.text}</span>
    </div>
  );
}
