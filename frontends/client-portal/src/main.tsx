import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { I18nProvider } from "./i18n";
import { registerServiceWorker } from "./pwa/registerServiceWorker";
import "./index.css";
import "./styles/neft-theme.css";
import "../../shared/brand/brand.css";

const base = import.meta.env.BASE_URL || "/client/";

registerServiceWorker();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter basename={base.replace(/\/$/, "")}>
      <I18nProvider>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </I18nProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
