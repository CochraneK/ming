// 明朝知识报告 · Service Worker
// 策略：仅拦截同源请求做 stale-while-revalidate（先返缓存、后台更新），重复访问秒开；
// 跨域资源（地图瓦片、unpkg Leaflet）一律不拦截，直接走原生网络。
// 注意：后台更新用 cache:'no-cache' 绕过浏览器 HTTP 缓存——否则 GitHub Pages 的
// max-age=600 会让 SWR 拿到陈旧响应，滞后被拉长到多个访问周期。
// CACHE 名 bump（v2）会在 activate 时清空旧缓存，强制老用户下次刷新立即得到新版。
const CACHE = 'ming-report-v2';

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

  // 跨域请求（地图瓦片、unpkg 等）不拦截：respondWith 转发会让
  // no-cors 图片请求永久 pending（表现为灰底红点）。跨域资源直接走原生网络。
  if (url.origin !== self.location.origin) return;

  // 同源：导航与资源走 stale-while-revalidate；后台更新绕过 HTTP 缓存
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req);
    const network = fetch(req, { cache: 'no-cache' }).then(res => {
      if (res && res.status === 200 && res.type === 'basic') cache.put(req, res.clone());
      return res;
    }).catch(() => cached);
    return cached || network || fetch(req);
  })());
});
