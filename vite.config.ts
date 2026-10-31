import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
 plugins:[react()],
 resolve:{alias:{'@i18n-runtime':fileURLToPath(new URL('./src/i18n-runtime',import.meta.url))}}
});
