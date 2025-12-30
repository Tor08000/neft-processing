import { CLIENT_BASE_PATH } from "../api/base";
import { isPwaMode } from "./mode";

export const registerServiceWorker = () => {
  if (!isPwaMode || !("serviceWorker" in navigator)) {
    return;
  }

  window.addEventListener("load", () => {
    const basePath = CLIENT_BASE_PATH || "/client";
    const swUrl = `${basePath}/sw.js`;
    navigator.serviceWorker.register(swUrl).catch(() => undefined);
  });
};
