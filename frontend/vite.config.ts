import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { resolve } from 'path';
 
 export default defineConfig({
  base: '/', // Use a relative base path for production
  build: {
    outDir: resolve(__dirname, '../backend/static/build'),
    emptyOutDir: true,
  },
   plugins: [react()],
   server: {
     proxy: {
       "/api": {
         target: process.env.VITE_API_BASE_URL || "http://127.0.0.1:8080",
         changeOrigin: true,
         secure: false,
       },
     },
   },
 });