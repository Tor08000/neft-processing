import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

function normalizeBasePath(rawBase: string | undefined): string {
  const withLeading = rawBase?.startsWith("/") ? rawBase : `/${rawBase ?? "client"}`;
  return withLeading.endsWith("/") ? withLeading : `${withLeading}/`;
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const base = normalizeBasePath(env.VITE_CLIENT_BASE_PATH);

  return {
    base,
    plugins: [react()],
    server: {
      port: 4174,
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/setupTests.ts",
    },
  };
});
