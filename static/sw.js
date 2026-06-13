// Tento skript běží na pozadí telefonu a stará se o to, aby se aplikace dala nainstalovat na plochu.
self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  return self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Jen propouštíme síťové dotazy, abychom zbytečně nakešovali stará data mrazáku
  e.respondWith(fetch(e.request));
});