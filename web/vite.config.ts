import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API + static thumbnails to the FastAPI backend on :8000,
// so the frontend is same-origin in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/files": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
