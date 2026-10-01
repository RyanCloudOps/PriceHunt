import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.API_URL || "http://localhost:8000",
    },
  },
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 800,
  },
});
