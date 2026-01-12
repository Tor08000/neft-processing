import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig(() => {
  return {
    base: "/admin/",
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
