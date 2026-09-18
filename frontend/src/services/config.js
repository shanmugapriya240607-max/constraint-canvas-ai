// Vite embeds only this public URL. Credentials must never use a VITE_ prefix.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "")
).replace(/\/+$/, "");
