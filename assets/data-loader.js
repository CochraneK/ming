/* ===== V5 在线数据加载器：boot 首屏 / full 深度数据 =====
   仅用于 web target。standalone.html 仍把完整 DATA / INSIGHT_DATA 内联，不加载本文件。 */
(function(){
'use strict';
if(typeof DATA==='undefined')return;

const root=document.documentElement;
let fullPromise=null;

function deepHashNeedsFull(){
  const raw=String(location.hash||'').replace(/^#/,'');
  if(!raw)return false;
  const params={};
  raw.split('&').forEach(part=>{
    if(!part)return;
    const i=part.indexOf('=');
    const k=i<0?part:part.slice(0,i);
    params[k]=i<0?'':decodeURIComponent(part.slice(i+1));
  });
  if(params.view&&params.view!=='overview')return true;
  return ['person','event','place','detail','map','era','net','from','to','q'].some(k=>params[k]!==undefined&&params[k]!=='');
}

function mark(mode,reason){
  root.dataset.mingData=mode;
  if(reason)root.dataset.mingDataReason=reason;
  else delete root.dataset.mingDataReason;
}

window.__MING_FULL_DATA_READY=window.__MING_FULL_DATA_READY===true;
mark(window.__MING_FULL_DATA_READY?'full':'boot');

window.__MING_ENSURE_FULL_DATA=function(reason){
  if(window.__MING_FULL_DATA_READY)return Promise.resolve(DATA);
  if(fullPromise)return fullPromise;
  mark('loading',reason||'interaction');
  fullPromise=new Promise((resolve,reject)=>{
    const script=document.createElement('script');
    script.src='assets/data-full.js';
    script.dataset.mingDataChunk='full';
    script.onload=()=>{
      if(!window.__MING_FULL_DATA_READY){
        reject(new Error('data-full.js 已加载但未标记 ready'));
        return;
      }
      try{if(typeof window.__MING_AFTER_FULL_DATA==='function')window.__MING_AFTER_FULL_DATA();}catch(_){}
      resolve(DATA);
    };
    script.onerror=()=>reject(new Error('完整数据加载失败'));
    document.head.appendChild(script);
  }).catch(err=>{
    fullPromise=null;mark('error',reason||'interaction');throw err;
  });
  return fullPromise;
};

/* 深链必须在 app.js 执行前拥有完整数据。当前脚本是 parser-blocking classic script，
   因而在 document 仍处于 loading 时用 document.write 插入同源 full chunk，可保证
   后面的 app.js 看到的是完整 DATA；普通首页绝不会走这条路径。 */
if(!window.__MING_FULL_DATA_READY&&document.readyState==='loading'&&deepHashNeedsFull()){
  mark('loading','deep-link');
  document.write('<script src="assets/data-full.js" data-ming-data-chunk="full"><\/script>');
  if(window.__MING_FULL_DATA_READY)mark('full','deep-link');
}
})();
