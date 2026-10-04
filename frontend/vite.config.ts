import { rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'
import { defineConfig } from 'vitest/config'

/**
 * `public/demo-data` (the static answers of the online demo) only belongs to the demo build
 * (`vite build --mode demo`): drop it from the regular build served by the local backend.
 */
function demoDataOnlyInDemo(mode: string): Plugin {
  let target: string | null = null
  return {
    name: 'premoulinette:demo-data-only-in-demo',
    apply: 'build',
    configResolved(config) {
      target = resolve(config.root, config.build.outDir, 'demo-data')
    },
    closeBundle() {
      if (mode !== 'demo' && target) rmSync(target, { recursive: true, force: true })
    },
  }
}

// The FastAPI backend (python -m premoulinette) listens on 127.0.0.1:8765.
// The proxy keeps the browser on a single origin during development.
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), demoDataOnlyInDemo(mode)],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8765', changeOrigin: false },
    },
  },
  preview: { port: 4173, strictPort: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    restoreMocks: true,
  },
}))
