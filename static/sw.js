const CACHE_NAME = 'fesco-v1';
const urlsToCache = ['/', '/static/index.html'];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('fetch', e => {
    // API calls skip karo (always fresh data)
    if (e.request.url.includes('/bill/') ||
        e.request.url.includes('/alert/') ||
        e.request.url.includes('/predict/')) {
        return;
    }

    e.respondWith(
        caches.match(e.request).then(response => response || fetch(e.request))
    );
});