import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// https://vitejs.dev/config/
const resolveBasePath = (env: Record<string, string>, fallback: string) => {
  const rawBase = env.VITE_PUBLIC_BASE || env.VITE_BASE_PATH || fallback;
  return rawBase.endsWith("/") ? rawBase : `${rawBase}/`;
};

const splitVendorChunk = (id: string) => {
  if (!id.includes("node_modules")) return undefined;
  if (id.includes("react-router-dom")) return "vendor-router";
  if (id.includes("@tanstack")) return "vendor-query";
  if (id.includes("leaflet")) return "vendor-map";
  if (id.includes("react")) return "vendor-react";
  return "vendor";
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    base: resolveBasePath(env, "/client/"),
    plugins: [react()],
    resolve: {
      alias: [
        { find: "react/jsx-dev-runtime", replacement: resolve(__dirname, "node_modules/react/jsx-dev-runtime.js") },
        { find: "react/jsx-runtime", replacement: resolve(__dirname, "node_modules/react/jsx-runtime.js") },
        { find: "react-router-dom", replacement: resolve(__dirname, "node_modules/react-router-dom") },
        { find: "react-dom", replacement: resolve(__dirname, "node_modules/react-dom") },
        { find: "react", replacement: resolve(__dirname, "node_modules/react") },
        { find: "@shared", replacement: resolve(__dirname, "../shared") },
      ],
      dedupe: ["react", "react-dom", "react-router-dom"],
    },
    server: {
      port: 4174,
      fs: {
        allow: [resolve(__dirname), resolve(__dirname, "../shared"), resolve(__dirname, "../../brand")],
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: splitVendorChunk,
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/setupTests.ts",
    },
  };
});
