import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The frontend talks to the FastAPI backend on :8000. Proxy API + health so the
// browser stays same-origin during development.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:8000",
      "/api": "http://localhost:8000",
    },
  },
});
