/// <reference types="vitest" />
import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  appType: 'spa',
  server: {
    port: 9873,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Keep the heavy charting stack (recharts + its d3 deps) in its own
        // cacheable chunk, loaded only when the Synthèse charts mount.
        manualChunks: (id) =>
          /node_modules\/(recharts|d3-|victory-vendor|internmap)/.test(id) ? 'charts' : undefined,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
});
