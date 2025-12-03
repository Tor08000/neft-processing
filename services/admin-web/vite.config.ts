import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

function normalizeBasePath(rawBase: string | undefined): string {
  const withLeading = rawBase?.startsWith("/") ? rawBase : `/${rawBase ?? "admin"}`;
  return withLeading.endsWith("/") ? withLeading : `${withLeading}/`;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const base = normalizeBasePath(env.VITE_ADMIN_BASE_PATH);

  return {
    base,
    plugins: [react()],
    resolve: {
      alias: {
        "react-router-dom": path.resolve(__dirname, "src/router/router-shim.tsx"),
      },
    },
    server: {
      host: true,
      port: 8080,
    },
    preview: {
      host: true,
      port: 8080,
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/setupTests.ts",
    },
  };
});
