import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

const apiProxy = {
	'/api': {
		target: 'http://127.0.0.1:8000',
		changeOrigin: true
	}
};

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		host: true,
		proxy: apiProxy
	},
	preview: {
		host: true,
		proxy: apiProxy
	}
});
