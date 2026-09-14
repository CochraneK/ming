/* ===== V13 在线数据加载器：实体详情分片 + 时间域 + 关系 metadata 分层 =====
   standalone.html 不加载本文件。关系索引只取可见 core；完整关系元数据仅 full DATA 再补。 */
(function(){
'use strict';
if(typeof DATA==='undefined')return;

const root=document.documentElement;
const CHARACTER_DETAIL_SHARD_COUNT=16;
const LOCATION_DETAIL_SHARD_COUNT=8;
const EVENT_DETAIL_SHARD_COUNT=8;
const CHARACTER_DETAIL_CHUNKS=Array.from({length:CHARACTER_DETAIL_SHARD_COUNT},(_,i)=>'character-detail-'+String(i).padStart(2,'0'));
const LOCATION_DETAIL_CHUNKS=Array.from({length:LOCATION_DETAIL_SHARD_COUNT},(_,i)=>'location-detail-'+String(i).padStart(2,'0'));
const EVENT_DETAIL_CHUNKS=Array.from({length:EVENT_DETAIL_SHARD_COUNT},(_,i)=>'event-detail-'+String(i).padStart(2,'0'));
const ALL_CHUNKS=['characters',...CHARACTER_DETAIL_CHUNKS,'locations',...LOCATION_DETAIL_CHUNKS,'place-chapters','voyages','events',...EVENT_DETAIL_CHUNKS,'relations','relation-meta','time','lifespans','graphs','insight','meta'];
const VIEW_CHUNKS={
  overview:[],distribution:[],
  visuals:['graphs'],
  locations:['locations'],
  map:['locations'],
  characters:['characters'],
  events:['events'],
  relations:['relations'],
  timeline:['time'],
  dynasty:['time'],
  chronicle:['lifespans','characters'],
  insight:['insight']
};
const chunkPromises=Object.create(null);
let searchPromise=null,fullPromise=null,_fullEventSent=false;
window.__MING_DATA_CHUNKS__=window.__MING_DATA_CHUNKS__||{};
window.__MING_CHARACTER_DETAILS__=window.__MING_CHARACTER_DETAILS__||{};
window.__MING_LOCATION_DETAILS__=window.__MING_LOCATION_DETAILS__||{};
window.__MING_EVENT_DETAILS__=window.__MING_EVENT_DETAILS__||{};
window.__MING_RELATION_META__=window.__MING_RELATION_META__||[];

function stableShardIndex(value,count){
  let h=5381>>>0;
  for(const ch of String(value||''))h=(Math.imul(h,33)^ch.codePointAt(0))>>>0;
  return h%count;
}
function characterDetailChunkFor(name){return 'character-detail-'+String(stableShardIndex(name,CHARACTER_DETAIL_SHARD_COUNT)).padStart(2,'0');}
function locationDetailChunkFor(name){return 'location-detail-'+String(stableShardIndex(name,LOCATION_DETAIL_SHARD_COUNT)).padStart(2,'0');}
function eventDetailChunkFor(id){return 'event-detail-'+String(stableShardIndex(id,EVENT_DETAIL_SHARD_COUNT)).padStart(2,'0');}
function resolveEventId(value){
  const raw=String(value||'');
  if(/^event-\d+$/.test(raw))return raw;
  const event=(DATA.events||[]).find(x=>x.id===raw||x.name===raw);
  return event&&event.id||'';
}
function entityPlan(kind,id){
  if(kind==='person')return ['characters',characterDetailChunkFor(id),'insight'];
  if(kind==='place')return ['locations',locationDetailChunkFor(id),'events','insight'];
  if(kind==='event'){
    const eventId=resolveEventId(id);
    return eventId?['events',eventDetailChunkFor(eventId),'locations','insight']:['events'];
  }
  return ALL_CHUNKS;
}
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

window.__MING_APPLY_CHARACTER_DETAILS__=function(){
  const details=window.__MING_CHARACTER_DETAILS__||{};let patched=0;
  (DATA.characters||[]).forEach(x=>{const extra=details[x&&x.name];if(extra){Object.assign(x,extra);patched++;}});
  root.dataset.mingCharacterDetails=String(patched);return patched;
};
window.__MING_APPLY_LOCATION_DETAILS__=function(){
  const details=window.__MING_LOCATION_DETAILS__||{};let patched=0;
  (DATA.locations||[]).forEach(x=>{const extra=details[x&&x.ancient];if(extra){Object.assign(x,extra);patched++;}});
  root.dataset.mingLocationDetails=String(patched);return patched;
};
window.__MING_APPLY_EVENT_DETAILS__=function(){
  const details=window.__MING_EVENT_DETAILS__||{};let patched=0;
  (DATA.events||[]).forEach(x=>{const extra=details[x&&x.id];if(extra){Object.assign(x,extra);patched++;}});
  root.dataset.mingEventDetails=String(patched);return patched;
};
window.__MING_APPLY_RELATION_META__=function(){
  const meta=window.__MING_RELATION_META__||[],rows=DATA.relations||[];
  if(!meta.length||meta.length!==rows.length)return 0;
  rows.forEach((x,i)=>Object.assign(x,meta[i]||{}));
  root.dataset.mingRelationMeta=String(rows.length);return rows.length;
};

window.__MING_SEARCH_INDEX_READY=window.__MING_SEARCH_INDEX_READY===true;
syncDataState();markSearch(window.__MING_SEARCH_INDEX_READY?'ready':'idle');
window.__MING_APPLY_CHARACTER_DETAILS__();window.__MING_APPLY_LOCATION_DETAILS__();window.__MING_APPLY_EVENT_DETAILS__();window.__MING_APPLY_RELATION_META__();

document.addEventListener('ming:data-chunk',event=>{
  const name=event&&event.detail&&event.detail.name;
  if(name==='characters'||String(name||'').startsWith('character-detail-'))window.__MING_APPLY_CHARACTER_DETAILS__();
  if(name==='locations'||String(name||'').startsWith('location-detail-'))window.__MING_APPLY_LOCATION_DETAILS__();
  if(name==='events'||String(name||'').startsWith('event-detail-'))window.__MING_APPLY_EVENT_DETAILS__();
  if(name==='relations'||name==='relation-meta')window.__MING_APPLY_RELATION_META__();
  syncDataState(name?'chunk:'+name:'chunk');
});

function loadChunk(name,reason){
  if(ready(name))return Promise.resolve(name);
  if(chunkPromises[name])return chunkPromises[name];
  chunkPromises[name]=new Promise((resolve,reject)=>{
    const script=document.createElement('script');
    script.src='assets/data-'+name+'.js';script.dataset.mingDataChunk=name;
    script.onload=()=>{
      if(!ready(name)){reject(new Error('data-'+name+'.js 已加载但未标记 ready'));return;}
      if(name==='characters'||name.startsWith('character-detail-'))window.__MING_APPLY_CHARACTER_DETAILS__();
      if(name==='locations'||name.startsWith('location-detail-'))window.__MING_APPLY_LOCATION_DETAILS__();
      if(name==='events'||name.startsWith('event-detail-'))window.__MING_APPLY_EVENT_DETAILS__();
      if(name==='relations'||name==='relation-meta')window.__MING_APPLY_RELATION_META__();
      syncDataState(reason||('chunk:'+name));resolve(name);
    };
    script.onerror=()=>reject(new Error('领域数据加载失败：'+name));
    document.head.appendChild(script);
  }).catch(err=>{delete chunkPromises[name];syncDataState('error:'+name);throw err;});
  return chunkPromises[name];
}

window.__MING_ENSURE_DATA_CHUNKS=function(names,reason){
  const wanted=uniq(names);
  if(!wanted.length){syncDataState(reason);return Promise.resolve(DATA);}
  root.dataset.mingData='loading';root.dataset.mingDataReason=reason||'interaction';
  return Promise.all(wanted.map(name=>loadChunk(name,reason))).then(()=>{
    window.__MING_APPLY_CHARACTER_DETAILS__();window.__MING_APPLY_LOCATION_DETAILS__();window.__MING_APPLY_EVENT_DETAILS__();window.__MING_APPLY_RELATION_META__();
    syncDataState(reason);
    try{if(typeof window.__MING_AFTER_DATA_CHUNKS==='function')window.__MING_AFTER_DATA_CHUNKS(wanted);}catch(_){}
    return DATA;
  });
};
window.__MING_VIEW_CHUNKS=VIEW_CHUNKS;
window.__MING_CHARACTER_DETAIL_CHUNK=characterDetailChunkFor;
window.__MING_LOCATION_DETAIL_CHUNK=locationDetailChunkFor;
window.__MING_EVENT_DETAIL_CHUNK=eventDetailChunkFor;
window.__MING_ENTITY_PLAN=entityPlan;
window.__MING_ENSURE_VIEW_DATA=function(view,reason){return window.__MING_ENSURE_DATA_CHUNKS(VIEW_CHUNKS[view]||ALL_CHUNKS,reason||('view:'+view));};
window.__MING_ENSURE_ENTITY_DATA=function(kind,reason,id){
  const why=reason||('entity:'+kind);
  if(kind!=='event')return window.__MING_ENSURE_DATA_CHUNKS(entityPlan(kind,id),why);
  return window.__MING_ENSURE_DATA_CHUNKS(['events'],why).then(()=>{
    const eventId=resolveEventId(id);
    if(!eventId)throw new Error('未找到事件：'+String(id||''));
    return window.__MING_ENSURE_DATA_CHUNKS([eventDetailChunkFor(eventId),'locations','insight'],why);
  });
};

window.__MING_ENSURE_SEARCH_INDEX=function(reason){
  if(window.__MING_SEARCH_INDEX_READY)return Promise.resolve(window.__MING_SEARCH_INDEX__||null);
  if(searchPromise)return searchPromise;
  markSearch('loading',reason||'command');
  searchPromise=new Promise((resolve,reject)=>{
    const script=document.createElement('script');script.src='assets/search-index.js';script.dataset.mingSearchChunk='index';
    script.onload=()=>{if(!window.__MING_SEARCH_INDEX_READY){reject(new Error('search-index.js 已加载但未标记 ready'));return;}markSearch('ready',reason||'command');resolve(window.__MING_SEARCH_INDEX__||null);};
    script.onerror=()=>reject(new Error('搜索索引加载失败'));document.head.appendChild(script);
  }).catch(err=>{searchPromise=null;markSearch('error',reason||'command');throw err;});
  return searchPromise;
};

window.__MING_ENSURE_FULL_DATA=function(reason){
  if(window.__MING_FULL_DATA_READY)return Promise.resolve(DATA);
  if(fullPromise)return fullPromise;
  fullPromise=window.__MING_ENSURE_DATA_CHUNKS(ALL_CHUNKS,reason||'full').then(data=>{
    window.__MING_APPLY_CHARACTER_DETAILS__();window.__MING_APPLY_LOCATION_DETAILS__();window.__MING_APPLY_EVENT_DETAILS__();window.__MING_APPLY_RELATION_META__();
    try{if(typeof window.__MING_AFTER_FULL_DATA==='function')window.__MING_AFTER_FULL_DATA();}catch(_){}return data;
  }).catch(err=>{fullPromise=null;throw err;});
  return fullPromise;
};

function readHash(){
  const raw=String(location.hash||'').replace(/^#/,'');const out={};if(!raw)return out;
  raw.split('&').forEach(part=>{if(!part)return;const i=part.indexOf('=');const k=i<0?part:part.slice(0,i);out[k]=i<0?'':decodeURIComponent(part.slice(i+1));});return out;
}
function deepPlan(){
  const p=readHash();
  if(p.person)return entityPlan('person',p.person);
  if(p.event)return entityPlan('event',p.event);
  if(p.place)return entityPlan('place',p.place);
  if(p.view&&p.view!=='overview')return VIEW_CHUNKS[p.view]||ALL_CHUNKS;
  return [];
}

/* deep link 在 app.js 前只预载视图/实体真正需要的数据；标准事件 deep link 使用稳定 event-* id。 */
if(document.readyState==='loading'){
  const plan=uniq(deepPlan()).filter(name=>!ready(name));
  if(plan.length){
    root.dataset.mingData='loading';root.dataset.mingDataReason='deep-link';
    plan.forEach(name=>document.write('<script src="assets/data-'+name+'.js" data-ming-data-chunk="'+name+'"><\/script>'));
  }
}
})();
