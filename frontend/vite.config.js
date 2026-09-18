import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const base = env.VITE_API_BASE_URL?.trim();
  if (command === "build" && mode === "production" && base) {
    let url;
    try { url = new URL(base); } catch { throw new Error("VITE_API_BASE_URL must be a public HTTPS origin"); }
    if (url.protocol !== "https:" || ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
        || url.hostname.endsWith(".localhost") || url.username || url.password
        || url.pathname !== "/" || url.search || url.hash) {
      throw new Error("VITE_API_BASE_URL must be a public HTTPS origin without a path or credentials");
    }
  }
  return {
  plugins: [react()],
  server: {
    port: 5173,
    host: "127.0.0.1",
  },
  resolve: {
    preserveSymlinks: true,
  },
  build: {
    rollupOptions: {
      preserveSymlinks: true,
    }
  }
  };
});
