import React from "react";
import { ToastMessage } from "./useToast";

export const Toast: React.FC<{ toast: ToastMessage | null }> = ({ toast }) => {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.kind}`}>
      <span>{toast.text}</span>
    </div>
  );
};
