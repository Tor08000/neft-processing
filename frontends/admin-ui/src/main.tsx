import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";
import "@shared/brand/brand.css";
import { applyTheme, getInitialTheme } from "./lib/theme";

const base = import.meta.env.BASE_URL || "/admin/";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

applyTheme(getInitialTheme());

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter basename={base.replace(/\/$/, "")}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
