// 明朝知识报告 · Service Worker
// 策略：仅拦截同源请求做 stale-while-revalidate（先返缓存、后台更新），重复访问秒开；
// 跨域资源（地图瓦片、unpkg Leaflet）一律不拦截，直接走原生网络。
// 注意：后台更新用 cache:'no-cache' 绕过浏览器 HTTP 缓存，避免 Pages max-age 放大陈旧窗口。
// CACHE 名 bump 会在 activate 时清空旧缓存，强制老用户下次刷新立即得到新版。
// v18：V9 人物详情 16 个 character-detail-* 确定性 shard。
// v19：V10 空间分层：locations + 8 个 location-detail-* + place-chapters + voyages。
// v20：V11 时间分层：lifespans 从 timeline 独立；年谱只缓存 characters + lifespans。
// v21：V12 事件分层：events 仅摘要，单事件详情进入 8 个 event-detail-*；时间轴/帝王只缓存 time。
// v22：V13 关系分层：relations 仅可见 core；relation-meta 只在完整 DATA 路径按需缓存。
// v23：恢复 pre-V1 classic UI；只换视觉/导航层，现代分片交付与懒加载保持不变。
const CACHE_PREFIX = 'ming-report-';
const CACHE = CACHE_PREFIX + 'v23';

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

  // classic UI 只改变可见外观；V13 交付策略保持：关系索引只取 relations core；
  // full DATA 才取 relation-meta；事件、人物、地点详情继续只缓存真正访问的对应 shard。
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
