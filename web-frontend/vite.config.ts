import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Skip non-node_modules
          if (!id.includes('node_modules')) {
            return;
          }

          // Syntax highlighter - lazy loaded on demand (check first, most specific)
          if (id.includes('react-syntax-highlighter') || id.includes('refractor') || id.includes('prismjs') || id.includes('lowlight') || id.includes('highlight.js')) {
            return 'vendor-syntax';
          }

          // React Router - loaded immediately (check before react)
          if (id.includes('react-router') || id.includes('@remix-run/router')) {
            return 'vendor-router';
          }

          // UI utilities
          if (id.includes('lucide-react') || id.includes('clsx')) {
            return 'vendor-ui';
          }

          // State management
          if (id.includes('zustand')) {
            return 'vendor-state';
          }

          // Core React + Markdown ecosystem (bundled together to avoid circular deps)
          // react-markdown imports React, so they must be in same chunk
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('scheduler') ||
              id.includes('react-markdown') || id.includes('remark') || id.includes('rehype') ||
              id.includes('unist') || id.includes('mdast') || id.includes('micromark') ||
              id.includes('hast') || id.includes('vfile')) {
            return 'vendor-react';
          }
        }
      }
    }
  }
})

