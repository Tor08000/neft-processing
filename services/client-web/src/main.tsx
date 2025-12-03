import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./index.css";

const base = import.meta.env.VITE_CLIENT_BASE_PATH || "/client/";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter basename={base.replace(/\/$/, "")}> 
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
