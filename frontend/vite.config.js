import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// 后端地址：host 直连 docker 暴露的端口默认 localhost:8000；
// docker 网络内可用 VOXAUDIT_API_TARGET=http://voxaudit_backend:8000 npm run dev
const API_TARGET = process.env.VOXAUDIT_API_TARGET || 'http://localhost:8000'

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
        target: API_TARGET,
        changeOrigin: true
      },
      '/upload_rules_template.json': {
        target: API_TARGET,
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})