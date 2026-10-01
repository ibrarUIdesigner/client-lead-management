import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5175,
    strictPort: true,
    proxy: {
      // Match the API prefix only. "/api" would also capture the /apify page.
      "/api/": "http://localhost:8000",
    },
  },
});
