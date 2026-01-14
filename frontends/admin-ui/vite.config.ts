import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

const resolveBasePath = (env: Record<string, string>, fallback: string) => {
  const rawBase = env.VITE_PUBLIC_BASE || env.VITE_BASE_PATH || fallback;
  return rawBase.endsWith("/") ? rawBase : `${rawBase}/`;
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    base: resolveBasePath(env, "/admin/"),
    plugins: [react()],
    resolve: {
      alias: {
        "@shared": resolve(__dirname, "../shared"),
      },
    },
    server: {
      host: true,
      port: 8080,
      fs: {
        allow: [resolve(__dirname), resolve(__dirname, "../shared"), resolve(__dirname, "../../brand")],
      },
    },
    preview: {
      host: true,
      port: 8080,
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/setupTests.ts",
      globals: true,
    },
  };
});
