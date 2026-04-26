import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/ws': { target: 'ws://localhost:8000', ws: true },
      '/sessions': { target: 'http://localhost:8000' },
      '/abort': { target: 'http://localhost:8000' },
      '/imgproxy': { target: 'http://localhost:8000' },
    },
  },
})
