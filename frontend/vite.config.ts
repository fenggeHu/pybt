import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Relax CSP only for local dev so Vite HMR code that uses eval-like helpers can run.
const devCsp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  // allow backend API and Vite HMR websocket
  "connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 http://127.0.0.1:8000/api http://localhost:8000/api ws://127.0.0.1:5173 ws://localhost:5173",
  "img-src 'self' data:",
  "object-src 'none'",
].join("; ");

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    headers: {
      "Content-Security-Policy": devCsp,
    },
  },
  // Keep preview consistent so `npm run preview` under CSP also works.
  preview: {
    port: 4173,
    headers: {
      "Content-Security-Policy": devCsp,
    },
  },
});
