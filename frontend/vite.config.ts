import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    // three.js (WebGL space scene) is inherently ~1 MB minified; split heavy
    // libs into long-lived vendor chunks for better caching, then raise the
    // warning ceiling since these are expected, not accidental, large deps.
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ["three", "@react-three/fiber"],
          charts: ["recharts"],
          motion: ["framer-motion"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});
