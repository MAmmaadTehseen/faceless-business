const STATIC = 'faceless-static-v1';
const SHELL = ['/offline.html', '/manifest.json', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/maskable-512.png', '/icons/apple-touch-icon.png'];
self.addEventListener('install', event => { event.waitUntil(caches.open(STATIC).then(cache => cache.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener('activate', event => { event.waitUntil(Promise.all([self.clients.claim(), caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('faceless-') && k !== STATIC).map(k => caches.delete(k))))])); });
const isStatic = url => url.origin === self.location.origin && (url.pathname.startsWith('/_next/static/') || SHELL.includes(url.pathname));
self.addEventListener('message', event => {
  if (event.data?.type !== 'ASSETS' || !Array.isArray(event.data.urls)) return;
  event.waitUntil(caches.open(STATIC).then(cache => Promise.all(event.data.urls.filter(u => { try { return isStatic(new URL(u)); } catch { return false; } }).map(u => cache.add(u).catch(() => {})))));
});
self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (isStatic(url)) {
    event.respondWith(caches.open(STATIC).then(async cache => {
      const cached = await cache.match(request); if (cached) return cached;
      const response = await fetch(request);
      if (response.ok) { await cache.put(request, response.clone()); if (/\.css(?:\?|$)/.test(url.href)) { const css = await response.clone().text(); const assets = [...css.matchAll(/url\(["']?([^)'"\s]+)["']?\)/g)].map(m => new URL(m[1], url)); await Promise.all(assets.filter(isStatic).map(u => cache.add(u.href).catch(() => {}))); } }
      return response;
    })); return;
  }
  // Authenticated pages and API data always go to the network; never persist private data.
  event.respondWith(fetch(request).catch(async () => request.mode === 'navigate' ? (await caches.match('/offline.html')) || Response.error() : new Response(JSON.stringify({ error: 'Offline' }), { status: 503, headers: { 'Content-Type': 'application/json' } })));
});
