import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  base: "/client/",
  plugins: [react()],
  server: {
    port: 4174,
  },
});
