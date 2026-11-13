import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// `npm run dev` forwards /api calls to the FastAPI backend. `npm run build` writes frontend/dist, which FastAPI serves.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
});
