import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { I18nProvider } from "./i18n";
import "./index.css";
import "@shared/brand/brand.css";
import { normalizeBase } from "@shared/lib/path";

const base = normalizeBase(import.meta.env.VITE_PUBLIC_BASE ?? "/partner");
document.documentElement.setAttribute("data-theme", "dark");

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
