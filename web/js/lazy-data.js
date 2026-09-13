/* ===== V5 深度视图门控 =====
   app.js 先用 boot payload 完成总览首屏；进入任何深度视图时再加载 full chunk。
   本文件必须位于 app.js 之后、experience.js 之前。 */
(function(){
'use strict';
if(typeof setView!=='function'||typeof state==='undefined'||typeof DATA==='undefined')return;
if(typeof window.__MING_ENSURE_FULL_DATA!=='function')return;

const baseSetView=setView;
let wantedView=null;
let loadToken=0;

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
  if(host)host.innerHTML='<div class="panel"><div class="empty" role="status" aria-live="polite">正在加载完整知识库…</div></div>';
  if(typeof syncTabA11y==='function')syncTabA11y();
  window.scrollTo(0,0);
}

function failLoad(err){
  const msg='完整知识库加载失败：'+String((err&&err.message)||err||'未知错误');
  if(typeof failBar==='function'){
    failBar('full-data',msg,{level:'error',retry:()=>location.reload(),retryLabel:'重新加载'});
  }
}

setView=function(view){
  if(view==='overview'||window.__MING_FULL_DATA_READY)return baseSetView(view);
  wantedView=view;
  const token=++loadToken;
  showLoading(view);
  window.__MING_ENSURE_FULL_DATA('view:'+view).then(()=>{
    if(token!==loadToken||wantedView!==view)return;
    rebuildLocationIndex();
    state.rendered[view]=false;
    wantedView=null;
    baseSetView(view);
  }).catch(failLoad);
};

window.__MING_AFTER_FULL_DATA=function(){
  rebuildLocationIndex();
  if(typeof checkDataCompleteness==='function')checkDataCompleteness(true);
};

document.addEventListener('ming:data-full',rebuildLocationIndex);
})();
