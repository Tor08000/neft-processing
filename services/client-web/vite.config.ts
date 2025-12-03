import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const base = env.VITE_CLIENT_BASE_PATH || "/client/";

  return {
    base,
    plugins: [react()],
    server: {
      port: 4174,
    },
  };
});
