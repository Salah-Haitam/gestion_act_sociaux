import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1", // force IPv4 : sous Windows "localhost" resout d'abord vers ::1
    port: 5173,
    proxy: {
      // Le front appelle "/api/..." : Vite relaie vers Django.
      // Evite tout probleme de CORS et de resolution IPv4/IPv6.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
