import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// https://vitejs.dev/config/
export default defineConfig(() => {
  return {
    base: "/client/",
    plugins: [react()],
    server: {
      port: 4174,
      fs: {
        allow: [resolve(__dirname), resolve(__dirname, "../shared"), resolve(__dirname, "../../brand")],
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/setupTests.ts",
    },
  };
});
