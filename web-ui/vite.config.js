import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 0.0.0.0으로 설정하여 외부에서도 접속 가능하게 합니다.
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // '/api'로 시작하는 모든 요청을 FastAPI(8000)로 전달합니다.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // 요청 주소에서 '/api'를 제거하고 전달합니다. (예: /api/status -> /status)
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
