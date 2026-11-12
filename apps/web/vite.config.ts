import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: true, allowedHosts: true, proxy: { "/api": api, "/media-files": api, "/mcp": api } },
});
