import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { I18nProvider } from "./i18n";
import { registerServiceWorker } from "./pwa/registerServiceWorker";
import "./index.css";
import "./styles/neft-client-brand.css";
import { applyTheme, getInitialTheme } from "./lib/theme";
import { normalizeBase } from "@shared/lib/path";

const base = normalizeBase(import.meta.env.VITE_PUBLIC_BASE ?? "/client");

registerServiceWorker();
applyTheme(getInitialTheme());

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter basename={base}>
      <I18nProvider>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </I18nProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
