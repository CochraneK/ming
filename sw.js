// 明朝知识报告 · Service Worker
// 策略：导航与同源资源 stale-while-revalidate（先返缓存、后台更新），
// 重复访问秒开；跨域（unpkg Leaflet）尽力缓存。任何失败都回退到网络，绝不返回错误页。
const CACHE = 'ming-report-v1';

self.addEventListener('install', () => { self.skipWaiting(); });

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // 同源：导航与资源走 stale-while-revalidate
  if (url.origin === self.location.origin) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(req);
      const network = fetch(req).then(res => {
        if (res && res.status === 200 && res.type === 'basic') cache.put(req, res.clone());
        return res;
      }).catch(() => cached);
      return cached || network || fetch(req);
    })());
    return;
  }

  // 跨域（unpkg 等）：能缓存则缓存，否则直接转发
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req);
    if (cached) return cached;
    try {
      const res = await fetch(req);
      if (res && res.status === 200) cache.put(req, res.clone());
      return res;
    } catch (_) {
      return cached || Response.error();
    }
  })());
});
