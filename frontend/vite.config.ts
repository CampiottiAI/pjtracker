import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

const apiProxy = {
	'/api': {
		target: 'http://127.0.0.1:8000',
		changeOrigin: true
	}
};

// mDNS / LAN hostnames (e.g. http://raspi.local:4173). IPs are already allowed.
const lanHosts = ['.local'];

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		host: true,
		allowedHosts: lanHosts,
		proxy: apiProxy
	},
	preview: {
		host: true,
		allowedHosts: lanHosts,
		proxy: apiProxy
	}
});
