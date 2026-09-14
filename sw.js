// 明朝知识报告 · Service Worker
// 策略：仅拦截同源请求做 stale-while-revalidate（先返缓存、后台更新），重复访问秒开；
// 跨域资源（地图瓦片、unpkg Leaflet）一律不拦截，直接走原生网络。
// 注意：后台更新用 cache:'no-cache' 绕过浏览器 HTTP 缓存，避免 Pages max-age 放大陈旧窗口。
// CACHE 名 bump 会在 activate 时清空旧缓存，强制老用户下次刷新立即得到新版。
// v13：V4 双交付：Pages 分离资源版 + standalone 单文件。
// v14：V5 boot/full 按需数据。
// v15：V6 搜索分层。
// v16：V7 视图领域分块。
// v17：V8 人物 cards / details 二级按需。
// v18：V9 人物详情 16 个确定性 shard。
// v19：V10 空间分层：地点摘要 + 8 个地点详情 shard + 按章节地点 + 航线独立按需。
const CACHE_PREFIX = 'ming-report-';
const CACHE = CACHE_PREFIX + 'v19';

self.addEventListener('install', () => { self.skipWaiting(); });
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.startsWith(CACHE_PREFIX) && k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // V10 仍只缓存用户实际访问过的块：地点页/默认地图先缓存 locations；打开单地再缓存
  // 一个 location-detail-*；“按章节”与 voyages 也各自独立，不会因进入地图就灌入整套空间数据。
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req);
    const network = fetch(req, { cache: 'no-cache' }).then(res => {
      if (res && res.status === 200 && res.type === 'basic') cache.put(req, res.clone());
      return res;
    }).catch(() => cached);
    if (cached) {
      event.waitUntil(network.catch(() => {}));
      return cached;
    }
    try { return await network; }
    catch (err) { return fetch(req); }
  })());
});
