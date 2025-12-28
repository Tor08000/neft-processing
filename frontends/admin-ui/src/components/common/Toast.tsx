import React from "react";
import { ToastMessage } from "../Toast/useToast";
import { Toast as BaseToast } from "../Toast/Toast";

export const Toast: React.FC<{ toast: ToastMessage | null }> = ({ toast }) => {
  return <BaseToast toast={toast} />;
};
