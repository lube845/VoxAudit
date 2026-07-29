import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 8888,
    proxy: {
      '/api': {
        target: 'http://voxaudit_backend:8000',
        changeOrigin: true
      },
      '/upload_rules_template.json': {
        target: 'http://voxaudit_backend:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})