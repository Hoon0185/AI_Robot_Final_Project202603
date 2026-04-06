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
      // '/api' 없이도 개별 API 경로를 감지하여 백엔드(8000)로 전달합니다.
      '^/(status|patrol|alerts|detections|inventory|products|waypoints|admin|robot)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
