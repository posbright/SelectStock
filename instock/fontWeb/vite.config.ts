import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    port: 3000,
    proxy: {
      // 代理后端 API
      '/api': {
        target: 'http://115.29.213.22:9988',
        changeOrigin: true
      },
      '/instock': {
        target: 'http://115.29.213.22:9988',
        changeOrigin: true
      },
      // 支持 /stock/ 前缀的代理（与生产环境 nginx 一致）
      '/stock/instock': {
        target: 'http://115.29.213.22:9988',
        changeOrigin: true,
        rewrite: (path: string) => path.replace(/^\/stock/, '')
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})
