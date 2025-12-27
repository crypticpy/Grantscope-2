/// <reference types="vitest" />
import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import sourceIdentifierPlugin from 'vite-plugin-source-identifier'

const isProd = process.env.BUILD_MODE === 'prod'
export default defineConfig({
  plugins: [
    react(),
    sourceIdentifierPlugin({
      enabled: !isProd,
      attributePrefix: 'data-matrix',
      includeProps: true,
    })
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
manualChunks: {
          // React core libraries
          'vendor-react': [
            'react',
            'react-dom',
            'react-router-dom',
            'scheduler'
          ],
          // React Flow - heavy visualization library
          'reactflow': [
            '@xyflow/react'
          ],
          // Date utilities
          'vendor-date': [
            'date-fns'
          ]
          // Note: Recharts/D3 are NOT manually chunked to avoid circular dep issues
        }
      }
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/components/visualizations/**/*.tsx'],
      exclude: ['src/components/visualizations/index.ts'],
    },
  },
})
