// 明朝知识报告 · Service Worker
// 策略：仅拦截同源请求做 stale-while-revalidate（先返缓存、后台更新），重复访问秒开；
// 跨域资源（地图瓦片、unpkg Leaflet）一律不拦截，直接走原生网络。
// 注意：后台更新用 cache:'no-cache' 绕过浏览器 HTTP 缓存——否则 GitHub Pages 的
// max-age=600 会让 SWR 拿到陈旧响应，滞后被拉长到多个访问周期。
// CACHE 名 bump（v6）会在 activate 时清空旧缓存，强制老用户下次刷新立即得到新版。
// v5：Phase 3~6 落地（统一实体 ID、模板拆分、deep link、搜索高亮、tab 语义）。
// v6：P2-03 势力结构化 / Phase 6 双模式图 / P2-10 时间轴区间 / P3-03 统一错误 UI / P3-01 体积压缩。
// v7：第六轮内容勘误（同名异地两级拆分：延安府 陕西/朝鲜、龙山 浙江/朝鲜；事件补年 7→2；地点定位 41→30）。
//     虽只改数据、前端未动，但 bump 可让老用户免于「SWR 首次返旧缓存」的一拍延迟，立即拿到新版数据。
// v8：洞察实体联动 + 书内语录扩面（app.js / app.css 有变更，属前端改动，必须 bump）。
// v9：自查轮修前端 2 处（详情弹窗里跳洞察要先关弹窗，否则被 top-layer 挡住；洞察链接找不到目标改为可见提示）
//     + 地点卡把「别称」与「书中提及」拆成两块渲染（app.js 有变更，必须 bump）。
const CACHE_PREFIX = 'ming-report-';
const CACHE = CACHE_PREFIX + 'v9';

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

  // 跨域请求（地图瓦片、unpkg 等）不拦截：respondWith 转发会让
  // no-cors 图片请求永久 pending（表现为灰底红点）。跨域资源直接走原生网络。
  if (url.origin !== self.location.origin) return;

  // 同源：导航与资源走 stale-while-revalidate。
  // 关键点：后台更新必须用 event.waitUntil() 保活——若只 return cached，
  // worker 生命周期可能在 fetch 完成前就结束，更新被中断，用户会长期看到旧版。
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
    try {
      return await network;
    } catch (err) {
      return fetch(req);   // 网络与缓存都失败时的最后兜底
    }
  })());
});
