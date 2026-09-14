/* ===== V12 视图 / 实体数据门控 =====
   app.js 用 boot 启动；人物/地点/事件均按“摘要 + 单实体详情 shard”加载。
   地点章节、郑和航线、lifespans 继续只在真正需要时加载。 */
(function(){
'use strict';
if(typeof setView!=='function'||typeof state==='undefined'||typeof DATA==='undefined')return;
if(typeof window.__MING_ENSURE_VIEW_DATA!=='function')return;

const baseSetView=setView;
const baseShowPerson=typeof showPerson==='function'?showPerson:null;
const baseShowEvent=typeof showEvent==='function'?showEvent:null;
const baseShowLocation=typeof showLocation==='function'?showLocation:null;
let wantedView=null,loadToken=0;

function chunksReady(names){return (names||[]).every(n=>window.__MING_DATA_CHUNKS__&&window.__MING_DATA_CHUNKS__[n]);}
function viewReady(view){return chunksReady((window.__MING_VIEW_CHUNKS||{})[view]||[]);}
function entityPlan(kind,id){
  if(typeof window.__MING_ENTITY_PLAN==='function')return window.__MING_ENTITY_PLAN(kind,id);
  return [];
}
function entityReady(kind,id){return chunksReady(entityPlan(kind,id));}
function chunkReady(name){return !!(window.__MING_DATA_CHUNKS__&&window.__MING_DATA_CHUNKS__[name]);}
function resolveEvent(value){
  const key=typeof value==='object'&&value?(value.id||value.name):value;
  return (DATA.events||[]).find(x=>x.id===key||x.name===key)||null;
}

function rebuildLocationIndex(){
  if(typeof LOC_INDEX==='undefined')return;
  Object.keys(LOC_INDEX).forEach(k=>delete LOC_INDEX[k]);
  (DATA.locations||[]).forEach(l=>{
    LOC_INDEX[l.ancient]=l;
    (l.mentionedAs||[]).forEach(a=>{if(!LOC_INDEX[a])LOC_INDEX[a]=l;});
  });
}
function showLoading(view){
  state.view=view;
  document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id===view));
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x.dataset.view===view));
  const host=document.getElementById(view);
  if(host)host.innerHTML='<div class="panel"><div class="empty" role="status" aria-live="polite">正在加载此视图所需数据…</div></div>';
  if(typeof syncTabA11y==='function')syncTabA11y();
  window.scrollTo(0,0);
}
function failLoad(err){
  const msg='所需数据加载失败：'+String((err&&err.message)||err||'未知错误');
  if(typeof failBar==='function')failBar('view-data',msg,{level:'error',retry:()=>location.reload(),retryLabel:'重新加载'});
}

setView=function(view){
  if(viewReady(view))return baseSetView(view);
  wantedView=view;const token=++loadToken;showLoading(view);
  window.__MING_ENSURE_VIEW_DATA(view,'view:'+view).then(()=>{
    if(token!==loadToken||wantedView!==view)return;
    if(chunkReady('locations'))rebuildLocationIndex();
    state.rendered[view]=false;wantedView=null;baseSetView(view);
  }).catch(failLoad);
};

function ensureEntity(kind,id,after){
  if(entityReady(kind,id)){after();return true;}
  window.__MING_ENSURE_ENTITY_DATA(kind,'entity:'+kind,id).then(()=>{
    if(chunkReady('locations'))rebuildLocationIndex();
    after();
  }).catch(failLoad);
  return true;
}
if(baseShowPerson){
  showPerson=function(name){
    return ensureEntity('person',name,()=>{const ok=baseShowPerson(name);if(ok===false&&typeof failBar==='function')failBar('person-missing','未找到人物：'+name,{level:'warn'});});
  };
}
if(baseShowEvent){
  showEvent=function(event){
    const key=event&&typeof event==='object'?(event.id||event.name):event;
    return ensureEntity('event',key,()=>{
      const actual=resolveEvent(key)||event;
      if(actual)baseShowEvent(actual);
      else if(typeof failBar==='function')failBar('event-missing','未找到事件：'+String(key||''),{level:'warn'});
    });
  };
}
if(baseShowLocation){showLocation=function(x){return ensureEntity('place',x&&x.ancient||x,()=>baseShowLocation(x));};}

/* 地点卡“详情”在 app.js 内直接 openDetail，不经过 showLocation：先补地点详情 shard。 */
document.addEventListener('click',e=>{
  const b=e.target&&e.target.closest?e.target.closest('[data-location-id]'):null;if(!b)return;
  const x=(DATA.locations||[]).find(y=>y.id===b.dataset.locationId);if(!x||entityReady('place',x.ancient))return;
  e.preventDefault();e.stopImmediatePropagation();
  window.__MING_ENSURE_ENTITY_DATA('place','location-card:'+x.ancient,x.ancient).then(()=>{rebuildLocationIndex();b.click();}).catch(failLoad);
},true);

/* 所有事件入口统一门控：事件索引、时间轴、帝王、人物/地点详情、航线都只在真正点击
   一条事件时补 events core + 目标 event-detail shard + locations + insight。 */
document.addEventListener('click',e=>{
  const b=e.target&&e.target.closest?e.target.closest('[data-event-id],[data-event-name],[data-loc-event]'):null;if(!b)return;
  const key=b.dataset.eventId||b.dataset.eventName||b.dataset.locEvent||'';
  if(entityReady('event',key))return;
  e.preventDefault();e.stopImmediatePropagation();
  window.__MING_ENSURE_ENTITY_DATA('event','event-click:'+key,key).then(()=>{
    if(chunkReady('locations'))rebuildLocationIndex();
    const event=resolveEvent(key);
    if(event)showEvent(event);else failLoad(new Error('未找到事件：'+key));
  }).catch(failLoad);
},true);

/* “按章节”只有切换到该模式才下载 chapterLocations。 */
document.addEventListener('click',e=>{
  const b=e.target&&e.target.closest?e.target.closest('[data-loc-mode="chapter"]'):null;if(!b||chunkReady('place-chapters'))return;
  e.preventDefault();e.stopImmediatePropagation();
  window.__MING_ENSURE_DATA_CHUNKS(['place-chapters'],'location-chapters').then(()=>b.click()).catch(failLoad);
},true);

/* 郑和航线的数据本身已经带停靠点事件摘要；切换模式只下载 voyages。点击具体事件时
   再由上面的统一事件门控取 event core + 单个详情 shard。 */
document.addEventListener('click',e=>{
  const b=e.target&&e.target.closest?e.target.closest('[data-map-mode="voyage"]'):null;if(!b||chunkReady('voyages'))return;
  e.preventDefault();e.stopImmediatePropagation();
  window.__MING_ENSURE_DATA_CHUNKS(['voyages'],'map-voyage').then(()=>b.click()).catch(failLoad);
},true);

/* 洞察正文在 capture 阶段先取对应实体计划；事件名称会先取 events core，再解析目标 shard。 */
document.addEventListener('click',e=>{
  const lnk=e.target&&e.target.closest?e.target.closest('.ins-link'):null;if(!lnk)return;
  const kind=lnk.hasAttribute('data-ins-p')?'person':(lnk.hasAttribute('data-ins-l')?'place':(lnk.hasAttribute('data-ins-e')?'event':''));
  if(!kind)return;
  const id=kind==='person'?lnk.getAttribute('data-ins-p'):(kind==='place'?lnk.getAttribute('data-ins-l'):lnk.getAttribute('data-ins-e'));
  if(entityReady(kind,id))return;
  e.preventDefault();e.stopImmediatePropagation();
  window.__MING_ENSURE_ENTITY_DATA(kind,'insight-link:'+kind,id).then(()=>{
    if(chunkReady('locations'))rebuildLocationIndex();
    lnk.click();
  }).catch(failLoad);
},true);

window.__MING_AFTER_DATA_CHUNKS=function(names){if((names||[]).includes('locations'))rebuildLocationIndex();};
window.__MING_AFTER_FULL_DATA=function(){rebuildLocationIndex();if(typeof checkDataCompleteness==='function')checkDataCompleteness(true);};
document.addEventListener('ming:data-chunk',e=>{if(e&&e.detail&&e.detail.name==='locations')rebuildLocationIndex();});
if(chunkReady('locations'))rebuildLocationIndex();
})();
