// CommuteCircle service worker: makes the app installable and opens instantly.
// The app shell (HTML, JS, CSS, icons) is cached; API calls always go to the network,
// so trip data, money and SOS are never served stale.
const CACHE = 'cc-shell-v1'
const SHELL = ['/', '/manifest.webmanifest', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()))
})

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return
  if (e.request.mode === 'navigate') {
    // Pages: network first (fresh deploys), cached shell when offline.
    e.respondWith(fetch(e.request).then((r) => { caches.open(CACHE).then((c) => c.put('/', r.clone())); return r })
      .catch(() => caches.match('/')))
    return
  }
  // Built assets have hashed names, so cache-first is safe.
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
    if (r.ok && url.pathname.startsWith('/assets/')) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)) }
    return r
  })))
})
