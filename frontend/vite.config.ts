import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev proxy target: local backend (uvicorn default port 8000).
// Matches backend default CORS origin http://localhost:5173 (Vite default port).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/files': 'http://localhost:8000',
    },
  },
})
