import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Optional: set host/port for the dev server
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173 },
});
