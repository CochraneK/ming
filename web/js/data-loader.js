/* ===== V7 在线数据加载器：boot / search / view-domain chunks =====
   standalone.html 不加载本文件；在线版的最终 DATA 被拆成互斥领域块，页面按需组合。 */
(function(){
'use strict';
if(typeof DATA==='undefined')return;

const root=document.documentElement;
const ALL_CHUNKS=['characters','events','space','relations','time','graphs','insight','meta'];
const VIEW_CHUNKS={
  overview:[],distribution:[],
  visuals:['graphs'],
  locations:['space','events','insight'],
  map:['space','events'],
  characters:['characters'],
  events:['events'],
  relations:['relations'],
  timeline:['time','events'],
  dynasty:['time','events'],
  chronicle:['time','characters'],
  insight:['insight']
};
const ENTITY_CHUNKS={
  person:['characters','events','insight'],
  place:['space','events','insight'],
  event:['events','space','insight']
};
const chunkPromises=Object.create(null);
let searchPromise=null,fullPromise=null,_fullEventSent=false;
window.__MING_DATA_CHUNKS__=window.__MING_DATA_CHUNKS__||{};

function uniq(items){return [...new Set((items||[]).filter(x=>ALL_CHUNKS.includes(x)))];}
function ready(name){return !!window.__MING_DATA_CHUNKS__[name];}
function readyNames(){return ALL_CHUNKS.filter(ready);}
function markSearch(mode,reason){
  root.dataset.mingSearch=mode;
  if(reason)root.dataset.mingSearchReason=reason;else delete root.dataset.mingSearchReason;
}
function syncDataState(reason){
  const names=readyNames();
  root.dataset.mingChunks=names.join(',');
  window.__MING_FULL_DATA_READY=names.length===ALL_CHUNKS.length;
  root.dataset.mingData=window.__MING_FULL_DATA_READY?'full':(names.length?'partial':'boot');
  if(reason)root.dataset.mingDataReason=reason;else delete root.dataset.mingDataReason;
  if(window.__MING_FULL_DATA_READY&&!_fullEventSent){
    _fullEventSent=true;
    document.dispatchEvent(new CustomEvent('ming:data-full'));
  }
}

window.__MING_SEARCH_INDEX_READY=window.__MING_SEARCH_INDEX_READY===true;
syncDataState();
markSearch(window.__MING_SEARCH_INDEX_READY?'ready':'idle');

/* 领域脚本自身只负责 Object.assign + 标记 ready。无论它来自动态 append 还是 deep-link
   document.write，都统一靠这个事件收敛 HTML 状态，避免 deep link 永久停在 loading。 */
document.addEventListener('ming:data-chunk',event=>{
  const name=event&&event.detail&&event.detail.name;
  syncDataState(name?'chunk:'+name:'chunk');
});

function loadChunk(name,reason){
  if(ready(name))return Promise.resolve(name);
  if(chunkPromises[name])return chunkPromises[name];
  chunkPromises[name]=new Promise((resolve,reject)=>{
    const script=document.createElement('script');
    script.src='assets/data-'+name+'.js';
    script.dataset.mingDataChunk=name;
    script.onload=()=>{
      if(!ready(name)){reject(new Error('data-'+name+'.js 已加载但未标记 ready'));return;}
      syncDataState(reason||('chunk:'+name));
      resolve(name);
    };
    script.onerror=()=>reject(new Error('领域数据加载失败：'+name));
    document.head.appendChild(script);
  }).catch(err=>{delete chunkPromises[name];syncDataState('error:'+name);throw err;});
  return chunkPromises[name];
}

window.__MING_ENSURE_DATA_CHUNKS=function(names,reason){
  const wanted=uniq(names);
  if(!wanted.length){syncDataState(reason);return Promise.resolve(DATA);}
  root.dataset.mingData='loading';
  root.dataset.mingDataReason=reason||'interaction';
  return Promise.all(wanted.map(name=>loadChunk(name,reason))).then(()=>{
    syncDataState(reason);
    try{if(typeof window.__MING_AFTER_DATA_CHUNKS==='function')window.__MING_AFTER_DATA_CHUNKS(wanted);}catch(_){}
    return DATA;
  });
};
window.__MING_VIEW_CHUNKS=VIEW_CHUNKS;
window.__MING_ENTITY_CHUNKS=ENTITY_CHUNKS;
window.__MING_ENSURE_VIEW_DATA=function(view,reason){return window.__MING_ENSURE_DATA_CHUNKS(VIEW_CHUNKS[view]||ALL_CHUNKS,reason||('view:'+view));};
window.__MING_ENSURE_ENTITY_DATA=function(kind,reason){return window.__MING_ENSURE_DATA_CHUNKS(ENTITY_CHUNKS[kind]||ALL_CHUNKS,reason||('entity:'+kind));};

window.__MING_ENSURE_SEARCH_INDEX=function(reason){
  if(window.__MING_SEARCH_INDEX_READY)return Promise.resolve(window.__MING_SEARCH_INDEX__||null);
  if(searchPromise)return searchPromise;
  markSearch('loading',reason||'command');
  searchPromise=new Promise((resolve,reject)=>{
    const script=document.createElement('script');
    script.src='assets/search-index.js';
    script.dataset.mingSearchChunk='index';
    script.onload=()=>{
      if(!window.__MING_SEARCH_INDEX_READY){reject(new Error('search-index.js 已加载但未标记 ready'));return;}
      markSearch('ready',reason||'command');resolve(window.__MING_SEARCH_INDEX__||null);
    };
    script.onerror=()=>reject(new Error('搜索索引加载失败'));
    document.head.appendChild(script);
  }).catch(err=>{searchPromise=null;markSearch('error',reason||'command');throw err;});
  return searchPromise;
};

window.__MING_ENSURE_FULL_DATA=function(reason){
  if(window.__MING_FULL_DATA_READY)return Promise.resolve(DATA);
  if(fullPromise)return fullPromise;
  fullPromise=window.__MING_ENSURE_DATA_CHUNKS(ALL_CHUNKS,reason||'full').then(data=>{
    try{if(typeof window.__MING_AFTER_FULL_DATA==='function')window.__MING_AFTER_FULL_DATA();}catch(_){}
    return data;
  }).catch(err=>{fullPromise=null;throw err;});
  return fullPromise;
};

function readHash(){
  const raw=String(location.hash||'').replace(/^#/,'');const out={};if(!raw)return out;
  raw.split('&').forEach(part=>{if(!part)return;const i=part.indexOf('=');const k=i<0?part:part.slice(0,i);out[k]=i<0?'':decodeURIComponent(part.slice(i+1));});
  return out;
}
function deepPlan(){
  const p=readHash();
  if(p.person)return ENTITY_CHUNKS.person;
  if(p.event)return ENTITY_CHUNKS.event;
  if(p.place)return ENTITY_CHUNKS.place;
  if(p.view&&p.view!=='overview')return VIEW_CHUNKS[p.view]||ALL_CHUNKS;
  return [];
}

/* deep link 必须在 app.js 之前拥有其视图所需的数据。classic parser-blocking script 中
   document.write 的同源脚本会按顺序执行；每个领域脚本触发 ming:data-chunk 后会同步状态。 */
if(document.readyState==='loading'){
  const plan=uniq(deepPlan()).filter(name=>!ready(name));
  if(plan.length){
    root.dataset.mingData='loading';root.dataset.mingDataReason='deep-link';
    plan.forEach(name=>document.write('<script src="assets/data-'+name+'.js" data-ming-data-chunk="'+name+'"><\/script>'));
  }
}
})();
