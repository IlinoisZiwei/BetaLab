import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { figmaSiteConfiguration } from './vite/plugins/figmaSiteConfiguration'
import { figmaErrorOverlayReplay } from './vite/plugins/figmaErrorOverlayReplay'
import { figmaReactRefreshBoundaryFallback } from './vite/plugins/figmaReactRefreshBoundaryFallback'
import { figmaMakeKitPlugin } from './vite/plugins/figmaMakeKitPlugin'
import { figmaLinkedPackageSourcemaps } from './vite/plugins/figmaLinkedPackageSourcemaps'

const apiTarget = process.env.BETALAB_API_TARGET || 'http://127.0.0.1:8788'

import siteConfiguration from './.figma/make/site.json'


// Vite config — https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // .figma/make/deploy-preview passes `--mode development` for cached-preview builds.
  const emitSourcemaps = mode === 'development'

  return {
    base: process.env.FIGMA_PUBLIC_URL ? `${process.env.FIGMA_PUBLIC_URL}/` : '/',
    build: {
      sourcemap: emitSourcemaps ? 'inline' : false,
      minify: !emitSourcemaps,
      rollupOptions: { input: { main: path.resolve(__dirname, 'index.html'), compute: path.resolve(__dirname, 'compute.html') } },
    },
    plugins: [
      react(),
      tailwindcss(),
      figmaSiteConfiguration(siteConfiguration),
      figmaErrorOverlayReplay(),
      figmaReactRefreshBoundaryFallback(),
      figmaMakeKitPlugin({ storiesGlob: '/src/**/*.stories.{ts,tsx,js,jsx}' }),
      figmaLinkedPackageSourcemaps(__dirname),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      // Private inputs/results must not bypass API authorization via Vite's file server.
      fs: { deny: ['.env', '.env.*', '*.{crt,pem}', '**/.git/**', '**/data/uploads/**',
        '**/data/compute/**', '**/backend/compute/runs/**', '**/local-server/jobs/**'] },
      proxy: {
        '/api/auth': { target: apiTarget, changeOrigin: true },
        '/api/users': { target: apiTarget, changeOrigin: true },
        '/api/health': { target: apiTarget, changeOrigin: true },
        '/api/profile': { target: apiTarget, changeOrigin: true },
        '/api/gyms': { target: apiTarget, changeOrigin: true },
        '/api/routes': { target: apiTarget, changeOrigin: true },
        '/api/tasks': { target: apiTarget, changeOrigin: true },
        '/api/notifications': { target: apiTarget, changeOrigin: true },
        '/api/videos': { target: apiTarget, changeOrigin: true },
        '/api': { target: 'http://127.0.0.1:8787', changeOrigin: true },
      },
      host: process.env.FIGMA_DEV_SERVER_HOST || '0.0.0.0',
      port: parseInt(process.env.PORT || '8443'),
      strictPort: true,
      watch: {
        ignored: [
          '**/.figma/**',
        ],
      },
    },
    preview: {
      host: process.env.FIGMA_DEV_SERVER_HOST || '0.0.0.0',
      port: parseInt(process.env.PORT || '8443'),
    },
  }
})
