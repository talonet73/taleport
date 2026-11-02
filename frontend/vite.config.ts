import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In dev the backend runs with `python -m taleport --dev` on a fixed port and Vite proxies /api.
const API_TARGET = 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    // Brand assets live in ../assets/brand, outside the Vite root.
    fs: { allow: ['..'] },
    proxy: { '/api': { target: API_TARGET, changeOrigin: true } },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
