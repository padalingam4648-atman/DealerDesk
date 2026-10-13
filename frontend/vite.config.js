import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite configuration for VIKMO DealerDesk Portal
// Base path is /portal/, outputting to frontend/dist/
// Proxy forwards /api requests to Django backend during local development
export default defineConfig({
  plugins: [react()],
  base: '/portal/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
