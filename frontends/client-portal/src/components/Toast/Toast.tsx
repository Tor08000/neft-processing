import type { ToastMessage } from "./useToast";

type ToastProps = {
  toast: ToastMessage | null;
  onClose?: () => void;
};

export function Toast({ toast, onClose }: ToastProps) {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.kind}`} role="status" aria-live="polite">
      <span>{toast.text}</span>
      {onClose ? (
        <button type="button" className="toast__close" aria-label="Close notification" onClick={onClose}>
          ×
        </button>
      ) : null}
    </div>
  );
}
