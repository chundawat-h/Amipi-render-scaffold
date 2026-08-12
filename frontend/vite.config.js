import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // API calls: /api/jobs → http://localhost:8000/jobs
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // Static output images: /outputs/job_1/hero.png → http://localhost:8000/outputs/job_1/hero.png
      '/outputs': {
        target: 'http://localhost:8000',
      },
    },
  },
})
