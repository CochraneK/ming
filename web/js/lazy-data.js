/* ===== V7 视图 / 实体领域数据门控 =====
   app.js 用 boot 启动；这里把 setView / show* 包装成按依赖加载，而不是一律拉完整知识库。 */
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
function entityReady(kind){return chunksReady((window.__MING_ENTITY_CHUNKS||{})[kind]||[]);}

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
    if(window.__MING_DATA_CHUNKS__&&window.__MING_DATA_CHUNKS__.space)rebuildLocationIndex();
    state.rendered[view]=false;wantedView=null;baseSetView(view);
  }).catch(failLoad);
};

function ensureEntity(kind,after){
  if(entityReady(kind)){after();return true;}
  window.__MING_ENSURE_ENTITY_DATA(kind,'entity:'+kind).then(()=>{
    if(window.__MING_DATA_CHUNKS__&&window.__MING_DATA_CHUNKS__.space)rebuildLocationIndex();
    after();
  }).catch(failLoad);
  return true;
}
if(baseShowPerson){
  showPerson=function(name){
    return ensureEntity('person',()=>{const ok=baseShowPerson(name);if(ok===false&&typeof failBar==='function')failBar('person-missing','未找到人物：'+name,{level:'warn'});});
  };
}
if(baseShowEvent){showEvent=function(event){return ensureEntity('event',()=>baseShowEvent(event));};}
if(baseShowLocation){showLocation=function(x){return ensureEntity('place',()=>baseShowLocation(x));};}

/* 洞察正文的原处理器会先 DATA.find 再调用 show*。若实体块尚未加载，必须在 capture
   阶段先补数据再重新触发点击，否则原处理器会误报“未找到”。 */
document.addEventListener('click',e=>{
  const lnk=e.target&&e.target.closest?e.target.closest('.ins-link'):null;if(!lnk)return;
  const kind=lnk.hasAttribute('data-ins-p')?'person':(lnk.hasAttribute('data-ins-l')?'place':(lnk.hasAttribute('data-ins-e')?'event':''));
  if(!kind||entityReady(kind))return;
  e.preventDefault();e.stopImmediatePropagation();
  window.__MING_ENSURE_ENTITY_DATA(kind,'insight-link:'+kind).then(()=>{
    if(window.__MING_DATA_CHUNKS__&&window.__MING_DATA_CHUNKS__.space)rebuildLocationIndex();
    lnk.click();
  }).catch(failLoad);
},true);

window.__MING_AFTER_DATA_CHUNKS=function(names){
  if((names||[]).includes('space'))rebuildLocationIndex();
};
window.__MING_AFTER_FULL_DATA=function(){
  rebuildLocationIndex();
  if(typeof checkDataCompleteness==='function')checkDataCompleteness(true);
};
document.addEventListener('ming:data-chunk',e=>{if(e&&e.detail&&e.detail.name==='space')rebuildLocationIndex();});
if(window.__MING_DATA_CHUNKS__&&window.__MING_DATA_CHUNKS__.space)rebuildLocationIndex();
})();
