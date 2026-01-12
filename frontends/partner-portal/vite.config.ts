import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// https://vitejs.dev/config/
export default defineConfig(() => {
  return {
    base: "/partner/",
    plugins: [react()],
    resolve: {
      alias: {
        "@shared": resolve(__dirname, "../shared"),
      },
    },
    server: {
      port: 4176,
      fs: {
        allow: [resolve(__dirname), resolve(__dirname, "../shared")],
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/setupTests.ts",
    },
  };
});
