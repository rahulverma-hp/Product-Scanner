import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

export default defineConfig({
  plugins: [react()],
  base: "/Product-Scanner/",
  server: {
    host: true,
    port: 5173,
    allowedHosts: ['unseductively-unprecedented-vanna.ngrok-free.dev'],
    proxy: {
      "/profiles": "http://localhost:5000",
      "/scan": "http://localhost:5000",
      "/auth": "http://localhost:5000",
      "/me": "http://localhost:5000",
    },
  }
});