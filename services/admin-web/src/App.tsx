import React from "react";
import { AuthProvider } from "./auth/AuthContext";
import { AppRouter } from "./router";

export function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}

export default App;
