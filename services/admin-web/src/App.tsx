import React, { Suspense } from "react";
import { AuthProvider } from "./auth/AuthContext";
import { AppRouter } from "./router";
import { Loader } from "./components/Loader/Loader";

export function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<Loader label="Загружаем интерфейс..." />}>
        <AppRouter />
      </Suspense>
    </AuthProvider>
  );
}

export default App;
