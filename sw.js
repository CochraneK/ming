// 明朝知识报告 · Service Worker
// 策略：仅拦截同源请求做 stale-while-revalidate（先返缓存、后台更新），重复访问秒开；
// 跨域资源（地图瓦片、unpkg Leaflet）一律不拦截，直接走原生网络。
// 注意：后台更新用 cache:'no-cache' 绕过浏览器 HTTP 缓存——否则 GitHub Pages 的
// max-age=600 会让 SWR 拿到陈旧响应，滞后被拉长到多个访问周期。
// CACHE 名 bump 会在 activate 时清空旧缓存，强制老用户下次刷新立即得到新版。
// v5：Phase 3~6 落地（统一实体 ID、模板拆分、deep link、搜索高亮、tab 语义）。
// v6：P2-03 势力结构化 / Phase 6 双模式图 / P2-10 时间轴区间 / P3-03 统一错误 UI / P3-01 体积压缩。
// v7：第六轮内容勘误（同名异地两级拆分：延安府 陕西/朝鲜、龙山 浙江/朝鲜；事件补年 7→2；地点定位 41→30）。
// v8：洞察实体联动 + 书内语录扩面。
// v9：详情/洞察联动与地点别称分级修复。
// v10：统一视觉层级与键盘焦点；web target 补齐资源。
// v11：V2 信息架构与跨视图视觉语言。
// v12：V3 全局快捷搜索、首页数据叙事、图谱阅读器。
// v13：V4 双交付：Pages 分离资源版 + standalone 单文件。
// v14：V5 boot/full 按需数据。
// v15：V6 搜索分层：打开搜索只取 search-index，选择实体后再取 full。
// v16：V7 视图领域分块：取消单一 data-full.js，人物/事件/空间/关系/时间/图谱/洞察/元数据独立缓存并按视图组合。
// v17：V8 人物二级按需：人物列表只缓存轻量 cards，打开详情后才缓存 character-details 补丁。
// v18：V9 人物详情确定性分片：全体详情拆为 16 个 character-detail-* shard，打开单人只缓存其所属 shard。
const CACHE_PREFIX = 'ming-report-';
const CACHE = CACHE_PREFIX + 'v18';

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

  // V9 继续沿用同源 SWR：人物索引先缓存 characters；真正打开人物时只缓存
  // 该姓名确定性命中的一个 character-detail-* shard，不会把 1231 人详情全部灌入缓存。
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
