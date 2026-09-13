const PARTS={p1:'壹部 · 洪武大帝',p2:'贰部 · 万国来朝',p3:'叁部 · 妖孽宫廷',p4:'肆部 · 粉饰太平',p5:'伍部 · 帝国飘摇',p6:'陆部 · 日暮西山',p7:'柒部 · 大结局'};
const REL_CAT_COLORS={'亲属':'#8d3025','君臣从属':'#b88b35','师生同门':'#706b91','同盟友党':'#527b5c','敌对冲突':'#a24b55','政治攻讦':'#476b86','婚姻姻亲':'#c06a8a','地点关联':'#8c6344','其他':'#9d9a8d'};
const EVENT_CAT_COLORS={'军事战争':'#8d3025','政治斗争':'#476b86','案件刑狱':'#706b91','人事任免':'#b88b35','制度科举':'#527b5c','外交边务':'#8c6344','宫廷变故':'#a24b55','民变起义':'#96502d','死亡身后':'#6f6a63','其他':'#9d9a8d'};
const relCatColor=c=>REL_CAT_COLORS[c]||'#9d9a8d';
const eventCatColor=c=>EVENT_CAT_COLORS[c]||'#9d9a8d';
const PART_COLORS={'p1':'#8d3025','p2':'#b88b35','p3':'#476b86','p4':'#527b5c','p5':'#8d5f42','p6':'#6d688c','p7':'#a24b55'};

// 地点反查表：ancient + mentioned_as -> 地点对象（用于事件地点 chip 跳地点详情）
const LOC_INDEX={};
DATA.locations.forEach(l=>{LOC_INDEX[l.ancient]=l;(l.mentionedAs||[]).forEach(a=>{if(!LOC_INDEX[a])LOC_INDEX[a]=l})});
document.addEventListener('click',e=>{const b=e.target.closest('[data-loc-chip]');if(b){const x=LOC_INDEX[b.dataset.locChip];if(x)showLocation(x)}});
document.addEventListener('click',e=>{const t=e.target.closest('#mgToggle');if(t){state.cleanExpanded=!state.cleanExpanded;state.rendered.overview=false;renderOverview();state.rendered.overview=true;}});
function eventLocationChips(ev){
  const s=ev.location||'';
  if(!s.trim())return '<span class="muted">未标注</span>';
  const toks=[...new Set(s.split(/[/、·,，（）()]/).map(t=>t.trim()).filter(Boolean))];
  return toks.map(t=>{const x=LOC_INDEX[t];return x?`<button class="link-button" data-loc-chip="${esc(t)}">${esc(t)}</button>`:`<span class="loc-text">${esc(t)}</span>`}).join('、');
}
const catBadge=(c,color)=>`<span class="cat-tag" style="--cat:${color}">${esc(c)}</span>`;
// 关系端点类型徽标：区分「东林党/东厂/后金」这类派系机构与「土木堡/皇觉寺」这类地点，
// 避免非人物端点看起来像真实人物。kind 由 merge 阶段判定（person/place/org/other）。
const epLabel=k=>k==='place'?'地点':k==='org'?'派系/机构':k==='regime'?'政权':k==='other'?'其他实体':'';
const epTag=(n,k)=>{const kk=k||(DATA.endpointKinds||{})[n];return (kk&&kk!=='person')?`<span class="ep-tag ep-${kk}">${epLabel(kk)}</span>`:'';};
const $=s=>document.querySelector(s);

/* ---- P3-03 统一错误 UI ----
   所有「可降级失败」共用同一条底部提示：role=alert/status + aria-live，
   统一带「重试」与「关闭」，按 key 去重（同一故障重复触发只更新文案，不堆叠）。
   设计原则：能继续用的功能绝不阻塞（地图挂了仍给离线点位图），但失败必须可见。 */
const _failBars={};
const _failSeen=Object.create(null);
function failHost(){
  let h=document.getElementById('failHost');
  if(!h){h=document.createElement('div');h.id='failHost';h.className='fail-host';document.body.appendChild(h);}
  return h;
}
function dismissFail(key){
  const bar=_failBars[key];
  if(!bar)return;
  delete _failBars[key];
  if(bar.parentNode)bar.parentNode.removeChild(bar);
  const h=document.getElementById('failHost');
  if(h&&!h.children.length&&h.parentNode)h.parentNode.removeChild(h);
}
/* level: error（红，需处理）| warn（黄，可降级）| info（灰，仅告知） */
function failBar(key,msg,opts){
  opts=opts||{};
  const level=opts.level==='error'?'fail-error':(opts.level==='warn'?'fail-warn':'fail-info');
  let bar=_failBars[key];
  if(!bar){
    bar=document.createElement('div');
    bar.setAttribute('role',level==='fail-error'?'alert':'status');
    bar.setAttribute('aria-live',level==='fail-error'?'assertive':'polite');
    const msgEl=document.createElement('span');msgEl.className='fail-msg';
    const acts=document.createElement('span');acts.className='fail-acts';
    bar.appendChild(msgEl);bar.appendChild(acts);
    if(opts.retry){
      const label=opts.retryLabel||'重试';
      const b=document.createElement('button');b.type='button';b.className='fail-act';b.textContent=label;
      b.addEventListener('click',()=>{
        b.disabled=true;b.textContent='重试中…';
        try{opts.retry();}catch(_){}
        setTimeout(()=>{b.disabled=false;b.textContent=label;},1200);
      });
      acts.appendChild(b);
    }
    if(opts.closable!==false){
      const c=document.createElement('button');c.type='button';c.className='fail-close';
      c.setAttribute('aria-label','关闭提示');c.textContent='×';
      c.addEventListener('click',()=>dismissFail(key));
      acts.appendChild(c);
    }
    _failBars[key]=bar;
    failHost().appendChild(bar);
  }
  bar.className='fail-bar '+level;
  const m=bar.querySelector('.fail-msg');
  if(m&&m.textContent!==msg)m.textContent=msg;
  return bar;
}
/* 运行时异常（脚本/异步/渲染）：同类异常只报一次，避免刷屏 */
function reportRuntimeError(kind,detail){
  const msg=(kind||'脚本')+'异常：'+String(detail||'未知错误').slice(0,160);
  if(_failSeen[msg])return;
  _failSeen[msg]=1;
  failBar('runtime',msg+'（页面其余部分仍可浏览）',{level:'error',retry:()=>location.reload(),retryLabel:'重新加载'});
}
// 搜索框绑定：防抖 + 输入法合成保护 + 重渲染后恢复焦点与光标。
// 直接监听 input 会全量重渲染整个区块、销毁输入框本身，导致中文输入法无法连续输入（每敲一个字母焦点就丢失）。
const _searchTimers={};
function bindSearch(sel,stateKey,onChange,delay){
  const el=$(sel);if(!el)return;
  let composing=false;
  const update=(force=false)=>{
    const v=el.value;
    if(!force&&state[stateKey]===v)return;
    state[stateKey]=v;
    clearTimeout(_searchTimers[sel]);
    _searchTimers[sel]=setTimeout(()=>{
      onChange();
      const n=$(sel);
      if(n){n.focus();try{n.setSelectionRange(n.value.length,n.value.length);}catch(_){}}
    },delay||220);
  };
  el.addEventListener('compositionstart',()=>{composing=true;clearTimeout(_searchTimers[sel]);});
  el.addEventListener('compositionend',()=>{composing=false;update(true);});
  el.addEventListener('input',e=>{if(!composing&&!e.isComposing)update();});
}
const displayText=value=>String(value==null?'':value).replace(/[\u2192\u21E2\u21D2\u279C\u279D\u279E]/g,'至').replace(/\u2190/g,'来自').replace(/\u2194/g,'关联');
const esc=value=>displayText(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
/* 统一搜索判定：直接子串命中，或命中的是别名（崇祯 → 朱由检）。
   各视图共用同一套别名索引 DATA.aliasIndex，避免每个列表各写一份。 */
function matchesQuery(hay,raw){const q=String(raw==null?'':raw).trim().toLowerCase();if(!q)return true;const h=String(hay||'').toLowerCase();if(h.includes(q))return true;const canon=(DATA.aliasIndex||{})[String(raw).trim()];return !!canon&&h.includes(String(canon).toLowerCase());}
const shortStatus=s=>{if(!s)return s;if(s.includes('待核验'))return '待核验';return s;};
const pageSize=36;
const state={dynastyEra:'',mapMode:'pilgrim',showMarkers:true,cleanExpanded:false,view:'overview',locMode:'index',locPage:1,locQuery:'',locRegion:'全部区域',chapterPage:1,distributionPage:1,distributionPart:'全部七部',distributionSort:'order',visualPart:'全部',visualPerson:'',netMode:'ego',charPage:1,charQuery:'',charPart:'',charFaction:'全部势力',charMinor:false,eventPage:1,eventQuery:'',eventType:'全部类型',eventCategory:'全部类别',relationPage:1,relationQuery:'',relationCategory:'全部类别',timelinePage:1,timelineCategory:'全部类别',timelineFrom:'',timelineTo:'',printMode:null,cardTheme:'thm-ink',rendered:{}};
const metrics=DATA.metrics;
const chapterLabel=key=>DATA.chapters[key]?.title||key;
const chapterChips=items=>(items||[]).slice(0,6).map(x=>`<span class="source-chip" title="${esc(x.title)}">${esc(x.title)}</span>`).join('')+((items||[]).length>6?`<span class="source-chip">+${items.length-6}章</span>`:'');
const pager=(page,total,size=pageSize)=>{const pages=Math.max(1,Math.ceil(total/size));return `<div class="pagination"><button data-page="prev" ${page<=1?'disabled':''}>上一页</button><span class="page-label">第 ${page} / ${pages} 页 · ${total} 条</span><button data-page="next" ${page>=pages?'disabled':''}>下一页</button></div>`};
const slicePage=(list,page)=>list.slice((page-1)*pageSize,page*pageSize);
function setView(view){state.view=view;document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id===view));document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x.dataset.view===view));if(!state.rendered[view]){({overview:renderOverview,distribution:renderDistribution,visuals:renderVisuals,locations:renderLocations,map:renderMap,characters:renderCharacters,events:renderEvents,relations:renderRelations,timeline:renderTimeline,dynasty:renderDynasty,chronicle:renderChronicle,insight:renderInsight}[view])();state.rendered[view]=true;}if(view==='map'){const mi=state.mapMode==='voyage'?voyageMapInstance:mapInstance;if(mi)setTimeout(()=>mi.invalidateSize(),60)}if(view==='visuals'&&state.netMode!=='ego'){setTimeout(()=>renderFullGraph(),30)}window.scrollTo(0,0)}
document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
document.addEventListener('click',e=>{const opener=e.target.closest('[data-open-view]');if(opener)setView(opener.dataset.openView)});
/* 翻面卡：全局委托一次，避免每次渲染人物页重复绑定导致点击失效 */
document.addEventListener('click',e=>{const flip=e.target.closest('[data-flip]');if(flip){e.preventDefault();const card=flip.closest('.character-card');if(card){const flipped=card.classList.toggle('flip');card.querySelector('.front').inert=flipped;card.querySelector('.back').inert=!flipped;}}});
/* 人物详情：唯一实现。人物页「详情」按钮、年谱人物名、URL deep link 共用，
   避免同一张卡在三个地方各写一份模板而慢慢长歪。 */
function personDetailHTML(x){
 const relHtml=(x.relations||[]).length?x.relations.map(r=>`<span class="rel ${r.dir}">${r.dir==='in'?'←':'→'} ${r.dir==='in'?esc(r.other)+' '+esc(r.rel):esc(r.rel)+' '+esc(r.other)}</span>${epTag(r.other,r.otherKind)}`).join('、'):'无';
 // P2-03：势力不再是一整串原文，而是逐项结构化展示；原串放在末行供回查（源透明）
 const p=x.profile||{};
 const chips=[];
 if(p.dynasty)chips.push(['朝代',p.dynasty]);
 if(p.regime)chips.push(['政权',p.regime]);
 if(p.period)chips.push(['时期',p.period]);
 if((p.factions||[]).length)chips.push(['派系',p.factions.join('、')]);
 if((p.orgs||[]).length)chips.push(['机构',p.orgs.join('、')]);
 if((p.categories||[]).length)chips.push(['身份类别',p.categories.join('、')]);
 const powerHtml=chips.length
   ?`<p class="profile-tags">${chips.map(([k,v])=>`<span class="profile-tag"><em>${esc(k)}</em>${esc(v)}</span>`).join('')}</p>${p.raw?`<p class="muted profile-raw">原串：${esc(p.raw)}</p>`:''}`
   :`<p>${esc(x.faction||'未标注')}</p>`;
 const extraBlocks=[];
 if((p.office||[]).length)extraBlocks.push(`<div class="detail-block"><strong>官职</strong><p>${esc(p.office.join('、'))}</p></div>`);
 if(p.origin)extraBlocks.push(`<div class="detail-block"><strong>籍贯</strong><p>${esc(p.origin)}</p></div>`);
 if(p.jinshi_year)extraBlocks.push(`<div class="detail-block"><strong>科举</strong><p>${esc(p.jinshi_year)} 年中进士</p></div>`);
 if(p.note)extraBlocks.push(`<div class="detail-block detail-wide"><strong>备注</strong><p>${esc(p.note)}</p></div>`);
 return `<div class="detail-grid"><div class="detail-block"><strong>身份</strong><p>${esc(x.role)}</p></div><div class="detail-block"><strong>生卒</strong><p>${esc(x.life)}</p></div><div class="detail-block"><strong>状态</strong><p>${esc(x.status)}</p></div><div class="detail-block detail-wide"><strong>势力 / 政治归属</strong>${powerHtml}</div>${extraBlocks.join('')}<div class="detail-block detail-wide"><strong>别名</strong><p>${esc((x.aliases||[]).join('、')||'无')}</p></div>${insightBlock('person',x.name)}<div class="detail-block detail-wide"><strong>涉及事件（${x.events.length}）</strong>${x.events.length?`<ul class="event-list">${x.events.slice(0,12).map(n=>`<li><button class="link-button" data-event-name="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul>`:`<p class="muted">书中未作为事件参与者出现。</p>`}</div><div class="detail-block detail-wide"><strong>同章上下文事件（${x.contextEvents.length}）</strong>${x.contextEvents.length?`<ul class="event-list">${x.contextEvents.slice(0,15).map(n=>`<li><button class="link-button" data-event-name="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul><p class="muted">书中同章提及，非本人物直接参与（可作关联线索）</p>`:`<p class="muted">同章亦无其它事件记录。</p>`}</div><div class="detail-block detail-wide"><strong>关系</strong><p>${relHtml}</p></div><div class="detail-block detail-wide"><strong>来源章节</strong><div class="source-row">${chapterChips(x.chapters.map(k=>({key:k,...DATA.chapters[k]})))}</div></div>${x.derivedCount?`<div class="detail-block detail-wide"><strong>出场口径</strong><p>共 ${x.chapters.length} 章，其中 ${x.derivedCount} 章为文本反查推导（本章正文出现至少 6 次自动登记，与 LLM 抽取区分）</p></div>`:''}</div>`;
}
function showPerson(name){
 const x=DATA.characters.find(y=>y.name===name);if(!x)return false;
 openDetail(x.name,personDetailHTML(x));bindEventNameClicks();
 writeHash({view:state.view,person:x.name,detail:'1'});
 return true;
}
function openDetail(title,html){$('#dialogTitle').textContent=title;$('#dialogContent').innerHTML=html;$('#detailDialog').showModal()}
$('#dialogClose').addEventListener('click',()=>$('#detailDialog').close());
$('#detailDialog').addEventListener('click',e=>{if(e.target.id==='detailDialog')$('#detailDialog').close()});
state.showMarkers=true;// 地点标记常显（原勾选框已按需求移除）
const mapSubnav=$('#mapSubnav');if(mapSubnav){mapSubnav.querySelectorAll('[data-map-mode]').forEach(b=>b.addEventListener('click',()=>{state.mapMode=b.dataset.mapMode;mapSubnav.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));renderMap()}))}
// 离线缓存：注册 Service Worker（stale-while-revalidate），重复访问秒开；失败不阻塞阅读，但给出可见提示。
if('serviceWorker' in navigator){
  window.addEventListener('load',()=>{
    const reg=()=>navigator.serviceWorker.register('sw.js')
      .then(()=>{dismissFail('sw');})
      .catch(()=>{failBar('sw','离线缓存未启用（离线打开与二次访问加速不可用），不影响当前阅读。',{level:'info',retry:reg});});
    reg();
    // 新版本就绪：提示刷新即可拿到最新数据
    navigator.serviceWorker.addEventListener('controllerchange',()=>{failBar('swUpdate','报告已更新到新版本，刷新即可加载最新内容。',{level:'info',retry:()=>location.reload(),retryLabel:'刷新'});});
  });
}
// 瓦片层工厂：主源 Esri（国内可达性好），连续 6 次出错且 0 张成功时自动回退 OSM。
const TILE_ESRI='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}';
const TILE_OSM='https://tile.openstreetmap.org/{z}/{x}/{y}.png';
function makeTiles(silent){
  const l=L.tileLayer(TILE_ESRI,{maxZoom:18,attribution:'Tiles © Esri'});
  let errs=0,oks=0,switched=false,reported=false;
  l.on('tileload',()=>{oks++;if(oks>0)dismissFail('tiles');});
  l.on('tileerror',()=>{
    errs++;
    if(errs>=6&&oks===0&&!switched){
      switched=true;errs=0;l.setUrl(TILE_OSM);
      if(!silent)failBar('tiles','底图主源（Esri）不可达，已自动切换到备用源 OSM。',{level:'info'});
      return;
    }
    if(switched&&errs>=14&&oks===0&&!reported){
      reported=true;
      if(silent)return;   // 后台预热失败不打扰用户；真正打开地图时会再报一次
      failBar('tiles','地图底图加载失败，地图上可能只见标记不见街道；请检查网络后重试。',{level:'warn',
        retry:()=>{switched=false;reported=false;errs=0;oks=0;l.setUrl(TILE_ESRI);l.redraw();}});
    }
  });
  return l;
}
// 地图资源后台预热：首屏空闲时预载 Leaflet，并用屏外隐藏地图把初始视野的瓦片
// 预热进浏览器缓存——用户点开地图时组件与瓦片都已就绪，基本零等待。
let _mapWarmed=false;
function warmMap(){
  if(_mapWarmed)return;_mapWarmed=true;
  loadLeaflet().then(()=>{
    try{
      const d=document.createElement('div');
      d.style.cssText='position:fixed;left:-9999px;top:-9999px;width:400px;height:300px;';
      document.body.appendChild(d);
      const m=L.map(d,{attributionControl:false,zoomControl:false}).setView([34.5,113],4);
      makeTiles(true).addTo(m);
      setTimeout(()=>{try{m.remove();}catch(_){}try{d.remove();}catch(_){}},4000);
    }catch(_){}
  }).catch(()=>{/* 后台预热失败不打扰用户：真正打开地图时 renderMap 会再报一次 */});
}
// 双保险：① 首屏空闲后台预热（主路径）；② 鼠标/手指一碰地图入口就立即预热，
// 避免 idle 回调被浏览器推迟时用户还要等。预热只做一次。
if('requestIdleCallback' in window){requestIdleCallback(warmMap,{timeout:6000});}else{setTimeout(warmMap,2500);}
document.querySelectorAll('[data-view="map"]').forEach(b=>{
  const kick=()=>warmMap();
  b.addEventListener('mouseenter',kick,{once:true});
  b.addEventListener('touchstart',kick,{once:true,passive:true});
});
function renderOverview(){
 $('#headerStat').textContent=`${metrics.chapters}章 · ${metrics.characters}人 · ${metrics.events}件事件 · ${metrics.relations}条关系`;
 $('#overview').innerHTML=`<div class="section-head"><div><h2>知识库总览</h2><p>${esc(DATA.scopeLabel)} · 抽取结果与人工整理的统一出口</p></div><span class="status draft">结果仍需史料核验</span></div><div class="summary-hero"><div class="hero-copy"><h2>${esc(DATA.scopeLabel)}</h2><p>从章节、人物、地点、事件、关系和时间六个入口查看同一份结构化数据。每条记录都保留来源章节，未定位地点与未知年份不会被静默丢弃。</p><div class="hero-note">来源章节 ${metrics.chapters} · 已定位地点 ${metrics.locatedLocations}/${metrics.locations} · 有数值年份事件 ${metrics.timedEvents}/${metrics.events}</div></div><div class="metric-grid"><div class="metric"><span class="value">${metrics.characters}</span><span class="label">人物实体</span></div><div class="metric"><span class="value">${metrics.locations}</span><span class="label">地点实体</span></div><div class="metric"><span class="value">${metrics.events}</span><span class="label">事件实体</span></div><div class="metric"><span class="value">${metrics.relations}</span><span class="label">关系记录</span></div></div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">数据状态</h2><p>输出口径明确区分实体总量、已定位数量和待核验记录。</p></div></div><div class="quality-grid"><div class="quality"><strong>${metrics.locatedLocations}/${metrics.locations} 个地点已定位</strong><span>其余地点仍可在地点索引和章节视图中查看</span></div><div class="quality"><strong>${metrics.unknownEvents} 件事件年份待考</strong><span>保留在事件索引，不会从结果中消失</span></div><div class="quality"><strong>${metrics.relations} 条关系完整保留</strong><span>关系索引支持分页查看，不在人物卡中截断</span></div><div class="quality"><strong>章节来源可追溯</strong><span>人物、地点、事件和关系均关联章节标题</span></div></div></div>`;
 $('#overview').insertAdjacentHTML('beforeend', distributionTeaser());
 $('#overview').insertAdjacentHTML('beforeend', cleaningPanel());
}
function cleaningPanel(){const c=DATA.cleaning||{};if(!c.relation_categories&&!c.person_merged_names)return '';const relTotal=Object.values(c.relation_categories||{}).reduce((a,b)=>a+b,0)||1;const evTotal=Object.values(c.event_categories||{}).reduce((a,b)=>a+b,0)||1;const relSegs=Object.entries(c.relation_categories||{}).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<span style="width:${(v*100/relTotal).toFixed(2)}%;background:${relCatColor(k)}" title="${esc(k)} ${v}条（${(v*100/relTotal).toFixed(1)}%）"></span>`).join('');const evSegs=Object.entries(c.event_categories||{}).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<span style="width:${(v*100/evTotal).toFixed(2)}%;background:${eventCatColor(k)}" title="${esc(k)} ${v}件（${(v*100/evTotal).toFixed(1)}%）"></span>`).join('');const relLegend=Object.entries(c.relation_categories||{}).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<span><i class="cat-dot" style="--cat:${relCatColor(k)};margin-right:4px"></i>${esc(k)} <b>${v}</b></span>`).join('');const evLegend=Object.entries(c.event_categories||{}).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<span><i class="cat-dot" style="--cat:${eventCatColor(k)};margin-right:4px"></i>${esc(k)} <b>${v}</b></span>`).join('');const merged=(c.person_merged_names||[]).map(n=>`<span class="source-chip">${esc(n)}</span>`).join('')||'<span class="muted">本轮无合并</span>';const mergeGroups=Object.entries(c.location_merge_groups||{});const MG_LIMIT=16;const mgShown=state.cleanExpanded?mergeGroups:mergeGroups.slice(0,MG_LIMIT);const mergeHtml=mergeGroups.length?mgShown.map(([k,v])=>`<span class="merge-chip"><b>${esc(k)}</b><i>←</i>${v.map(x=>`<em>${esc(x)}</em>`).join('、')}</span>`).join('')+(mergeGroups.length>MG_LIMIT?`<button class="merge-more" id="mgToggle">${state.cleanExpanded?'收起 ▲':'展开其余 '+(mergeGroups.length-MG_LIMIT)+' 组 ▼'}</button>`:''):'<span class="muted">无</span>';return `<div class="panel"><div class="section-head"><div><h2 style="font-size:18px">数据清洗与分类</h2><p>同一人物异名、同城古地名已在聚合层合并；关系与事件的自由文本标签归入固定类别。</p></div><span class="status">聚合层处理</span></div><div class="clean-grid"><div class="clean-card"><strong>人物同名合并 ${c.person_merged_names?c.person_merged_names.length:0} 组</strong><span>异名并入规范名，章节与别名保留</span><div class="clean-chips">${merged}</div></div><div class="clean-card span-2"><strong>地点同城合并 ${mergeGroups.length} 组 · 自环剔除 ${c.selfloop_dropped||0} 条</strong><div class="merge-chips">${mergeHtml}</div></div><div class="clean-card"><strong>关系类别归一 ${relTotal} 条</strong><div class="cat-dist">${relSegs}</div><div class="cat-legend">${relLegend}</div></div><div class="clean-card"><strong>事件类别归一 ${evTotal} 件</strong><div class="cat-dist">${evSegs}</div><div class="cat-legend">${evLegend}</div></div></div></div>`;}
function renderInsight(){
  const D=INSIGHT_DATA;
  if(!D||!D.sections||!D.sections.length){$('#insight').innerHTML='<div class="empty">暂无洞察数据</div>';return;}
  // 学科主题色：目录卡/徽标/章节顶边共用（综合=金，收束全篇）
  const DISC_COLORS={history:'#8d3025',psychology:'#706b91',museum:'#8c6344',politics:'#476b86',sociology:'#527b5c',anthropology:'#96502d',systems:'#356f9c',economics:'#7a5ca8',geography:'#3d7a7a',law:'#a24b55',military:'#4f7d3a',narrative:'#b0466f',gender:'#9a6b2f',ideology:'#443a8c',diplomacy:'#2e7d64',science:'#8c2f7a',art:'#c2571f',info:'#6a7f3c',synthesis:'#b88b35'};
  const discColor=s=>DISC_COLORS[s.id]||'#9d9a8d';
  const toc=D.sections.map((s,idx)=>{const c=discColor(s);return `<a class="insight-toc-card${s.id==='synthesis'?' ins-toc-synthesis':''}" href="#ins-${s.id}" style="--disc:${c}"><span class="ins-toc-num">${String(idx+1).padStart(2,'0')}</span><span class="ins-toc-meta"><span class="ins-toc-disc">${esc(s.discipline)}${s.id==='synthesis'?' · 收束':''}</span><span class="ins-toc-title">${esc(s.title)}</span></span></a>`}).join('');
  const secs=D.sections.map((s,idx)=>{const c=discColor(s);return `<article class="insight-sec${s.id==='synthesis'?' insight-sec-synthesis':''}" id="ins-${s.id}" style="--disc:${c}"><div class="insight-sec-head"><span class="insight-badge" style="color:${c};background:${c}14;border-color:${c}55">${esc(s.discipline)}</span><span class="ins-sec-num">${String(idx+1).padStart(2,'0')} / ${D.sections.length}</span><h3>${esc(s.title)}</h3></div>${s.html}</article>`}).join('');
  const refs=D.refs.map(r=>`<li>${r}</li>`).join('');
  const lastSec=D.sections[D.sections.length-1];
  $('#insight').innerHTML=`<div class="section-head"><div><h2>跨学科洞察报告</h2><p>基于《明朝那些事儿》知识图谱（${metrics.chapters} 章 · ${metrics.characters} 人物 · ${metrics.locations} 地点 · ${metrics.events} 事件 · ${metrics.relations} 关系）的 ${D.sections.length-1} 学科交叉解读，末章「${esc(lastSec?lastSec.discipline:'综合')}」收束全篇。文内引用采用 APA 格式，参考文献列于文末。</p></div><span class="status draft">交叉解读 · 供批判性阅读</span></div><nav class="insight-toc" aria-label="学科目录"><div class="insight-toc-head"><strong>目录 · ${D.sections.length} 镜</strong><span>点击卡片直达 · 综合收束于末</span></div><div class="insight-toc-grid">${toc}</div></nav><div class="insight-body">${secs}</div><section class="insight-refs"><div class="section-head"><div><h3>参考文献（APA 7）</h3><p>含主源《明朝那些事儿》与各学科支撑文献；数据集以本项目聚合结果为准。</p></div></div><ol class="insight-ref-list">${refs}</ol></section>`;
  linkifyInsight();
}
function distributionTeaser(){const d=DATA.distribution,s=d.stats,total=s.total,highest=[...d.chapters].sort((a,b)=>b.density-a.density)[0],lowest=[...d.chapters].sort((a,b)=>a.density-b.density)[0];return `<div class="panel distribution-teaser"><div class="section-head"><div><h2 style="font-size:18px">抽取分布诊断</h2><p>${esc(d.judgement.overall)} 详细分部、章节、密度和层级结构见“分布”。</p></div><button class="action" data-open-view="distribution">查看分布</button></div><div class="distribution-stat-grid"><div class="distribution-stat"><strong>CV ${total.cv}</strong><span>章节总抽取量的相对离散度</span></div><div class="distribution-stat"><strong>密度 ${s.density.cv}</strong><span>每万字密度的相对离散度</span></div><div class="distribution-stat"><strong>${esc(highest.title)}</strong><span>最高密度 ${highest.density}/万字</span></div><div class="distribution-stat"><strong>${esc(lowest.title)}</strong><span>最低密度 ${lowest.density}/万字</span></div></div></div>`}
function renderDistribution(){const d=DATA.distribution,s=d.stats,labels={characters:'人物',locations:'地点',events:'事件',relations:'关系'},colors={characters:'legend-character',locations:'legend-location',events:'legend-event',relations:'legend-relation'},sortLabels={order:'原书章节顺序',total:'总量从高到低',density:'密度从高到低',characters:'人物数从高到低',locations:'地点数从高到低',events:'事件数从高到低',relations:'关系数从高到低'};const chapterRows=d.chapters.map((item,index)=>({...item,_index:index}));const filtered=chapterRows.filter(item=>state.distributionPart==='全部七部'||item.partKey===state.distributionPart);const sorted=[...filtered].sort((a,b)=>{if(state.distributionSort==='order')return a._index-b._index;return b[state.distributionSort]-a[state.distributionSort]||a._index-b._index});const distPageSize=12;const page=sorted.slice((state.distributionPage-1)*distPageSize,state.distributionPage*distPageSize);const maxPart=Math.max(...d.parts.map(x=>x.total),1),maxChapter=Math.max(...chapterRows.map(x=>x.total),1),maxDensity=Math.max(...chapterRows.map(x=>x.density),1);const segment=(item,key,extra='')=>`<span class="${extra||'part-segment'} ${colors[key]}" style="width:${item.total?item[key]*100/item.total:0}%" title="${labels[key]} ${item[key]}"></span>`;const parts=d.parts.map(item=>`<div class="part-row"><div class="part-label"><strong>${esc(item.part)}</strong><span>${item.chapters}章 · 占章节抽取量 ${item.share}%</span></div><div class="part-bar" style="width:${item.total*100/maxPart}%">${segment(item,'characters')}${segment(item,'locations')}${segment(item,'events')}${segment(item,'relations')}</div><div class="part-values">${item.total}</div><div class="part-density">${item.density}/万字</div></div>`).join('');const chapterItems=page.map(item=>`<div class="chapter-row"><div class="chapter-name"><strong title="${esc(item.title)}">${esc(item.title)}</strong><span>${esc(item.part)} · ${item.textLength.toLocaleString()}字</span></div><div class="chapter-bars"><div class="chapter-track" style="width:${item.total*100/maxChapter}%">${segment(item,'characters','chapter-segment legend-character')}${segment(item,'locations','chapter-segment legend-location')}${segment(item,'events','chapter-segment legend-event')}${segment(item,'relations','chapter-segment legend-relation')}</div><div class="density-track" title="每万字 ${item.density}"><span style="width:${item.density*100/maxDensity}%"></span></div></div><div class="chapter-value">${item.total}条</div><div class="chapter-density">${item.density}/万</div></div>`).join('')||'<div class="empty">没有匹配章节</div>';const eraByPart=DATA.eraByPart||[];const eraMax=Math.max(...eraByPart.map(r=>r.total),1);const _pre=(DATA.reigns||[]).length?DATA.reigns[0].start:1368;const eraLegend='<span><i class="legend-dot" style="background:#9d9a8d"></i>明兴之前（'+_pre+' 前）</span>'+(DATA.reigns||[]).map((r,i)=>`<span><i class="legend-dot" style="background:${reignColor(i)}"></i>${esc(r.era)}</span>`).join('')+'<span><i class="legend-dot" style="background:#9d9a8d"></i>甲申之后（1644 后）</span>';const eraRows=eraByPart.map(r=>`<div class="part-row"><div class="part-label"><strong>${esc(r.part)}</strong><span>可纪年事件 ${r.total} 件 · ${r.segCount} 个年号段</span></div><div class="part-bar" style="width:${r.total*100/eraMax}%">${r.segments.map(sg=>`<span class="part-segment" style="width:${sg.count*100/r.total}%;background:${sg.order===0||sg.order===99?'#9d9a8d':reignColor(sg.order-1)}" title="${esc(sg.era)} · ${sg.count} 件"></span>`).join('')}</div><div class="part-values">${r.total}</div><div class="part-density">${r.segCount}段</div></div>`).join('')||'<div class="empty">暂无可纪年事件</div>';const entities=d.layers.entities.map(item=>`<li>${esc(item.label)} ${item.count}个实体 · ${item.chapterTotal}章次抽取</li>`).join('');const evidence=d.layers.evidence.map(item=>`<li>${esc(item.label)} ${item.count} · ${esc(item.detail)}</li>`).join('');$('#distribution').innerHTML=`<div class="section-head"><div><h2>抽取分布与层级</h2><p>${esc(DATA.scopeLabel)} · 章节级原始抽取诊断，和全局实体结果分开计数。</p></div><span class="status draft">分布不等于质量结论</span></div><div class="distribution-intro"><div class="distribution-callout"><span class="signal">判断</span><h3>${esc(d.judgement.overall)}</h3><p>总体 CV ${s.total.cv}；地点 CV ${s.locations.cv}，密度 CV ${s.density.cv}。最高与最低密度相差 ${d.judgement.densityRatio} 倍，说明章节长度和内容类型都需要纳入解释。</p></div><div class="distribution-stat-grid"><div class="distribution-stat"><strong>${s.total.median}</strong><span>章节总量中位数 · P25 ${s.total.p25} / P75 ${s.total.p75}</span></div><div class="distribution-stat" title="CV=标准差÷均值，衡量各章之间分布的不均程度（>0.5 即明显不均）。四维=人物/地点/事件/关系，此处取 CV 最大者。"><strong>${s[d.judgement.strongestDimension] ? s[d.judgement.strongestDimension].cv : s.locations.cv}</strong><span>${({characters:'人物',locations:'地点',events:'事件',relations:'关系'})[d.judgement.strongestDimension]||'地点'}数 CV · 四类中最不均匀</span></div><div class="distribution-stat"><strong>${s.density.max}</strong><span>最高每万字密度</span></div><div class="distribution-stat"><strong>${s.density.min}</strong><span>最低每万字密度</span></div></div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">一、分部层</h2><p>横向长度按分部总抽取量共享尺度，条内按人物、地点、事件、关系组成。</p></div></div><div class="distribution-legend"><span><i class="legend-dot legend-character"></i>人物</span><span><i class="legend-dot legend-location"></i>地点</span><span><i class="legend-dot legend-event"></i>事件</span><span><i class="legend-dot legend-relation"></i>关系</span><span>右侧为总量 / 每万字密度</span></div><div class="distribution-scale"><span>分部总抽取量</span><span>最大 ${maxPart} 条</span></div><div class="part-list">${parts}</div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">二、章节层</h2><p>四类计数均为章节内唯一项；上条为总量，下条为每万字密度。</p></div></div><div class="toolbar"><label>部次</label><select id="distPart"><option>全部七部</option>${d.parts.map(x=>`<option value="${x.partKey}" ${state.distributionPart===x.partKey?'selected':''}>${esc(x.part)}</option>`).join('')}</select><label>排序</label><select id="distSort">${Object.entries(sortLabels).map(([key,label])=>`<option value="${key}" ${state.distributionSort===key?'selected':''}>${label}</option>`).join('')}</select><span class="muted grow">共 ${filtered.length} 章 · 总量条形共享尺度 ${maxChapter} 条 · 密度按正文长度折算</span></div><div class="chapter-header"><span>章节</span><span>总量 / 密度</span><span>总量</span><span>每万字</span></div><div class="chapter-list-dist">${chapterItems}</div>${pager(state.distributionPage,sorted.length,distPageSize)}</div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">三、结果层级</h2><p>从来源章节到实体、关系网络，再落到可回溯的证据入口。</p></div></div><div class="layer-flow"><div class="layer-node"><small>01 · SOURCE</small><strong>${esc(d.layers.source.label)}</strong><b>${d.layers.source.count}章</b><span>${esc(d.layers.source.detail)}</span></div><div class="layer-connector" aria-hidden="true"></div><div class="layer-node"><small>02 · ENTITIES</small><strong>实体抽取</strong><b>${d.layers.entities.length}类</b><ul class="layer-list">${entities}</ul></div><div class="layer-connector" aria-hidden="true"></div><div class="layer-node"><small>03 · NETWORK</small><strong>${esc(d.layers.network.label)}</strong><b>${d.layers.network.count}条</b><span>章节内合计 ${d.layers.network.chapterTotal} 条关系抽取。</span></div><div class="layer-connector" aria-hidden="true"></div><div class="layer-node"><small>04 · TRACE</small><strong>来源追溯</strong><b>${d.layers.evidence.length}类</b><ul class="layer-list">${evidence}</ul></div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">四、分部 × 年号</h2><p>可纪年事件按来源分部与在位年号段堆叠；条宽按总量共享尺度，悬停查看各段件数。</p></div></div><div class="distribution-legend">${eraLegend}</div><div class="part-list">${eraRows}</div></div><div class="distribution-foot">口径说明：章节层按单章内唯一姓名、地点古名、事件名、关系三元组计数；实体层按合并后的全局实体计数，跨章节重复出现不会被误加成实体总数。</div></div>`;$('#distPart').addEventListener('change',e=>{state.distributionPart=e.target.value;state.distributionPage=1;renderDistribution()});$('#distSort').addEventListener('change',e=>{state.distributionSort=e.target.value;state.distributionPage=1;renderDistribution()});const root=$('#distribution');bindPaging(root,delta=>{state.distributionPage+=delta;renderDistribution()})}
function renderVisuals(){
 const visuals=DATA.visualizations,heat=visuals.characterHeatmap,evolution=visuals.eventTypeEvolution,network=visuals.relationNetwork;
 const partKeys=[...new Set(heat.chapters.map(x=>x.partKey))].sort((a,b)=>Number(a.slice(1))-Number(b.slice(1)));const partOptions=`<option value="全部" ${state.visualPart==='全部'?'selected':''}>全部范围</option>${partKeys.map(key=>`<option value="${key}" ${state.visualPart===key?'selected':''}>${esc(PARTS[key]||key)}</option>`).join('')}`;
 const chapters=heat.chapters.filter(x=>state.visualPart==='全部'||x.partKey===state.visualPart);const chapterSet=new Set(chapters.map(x=>x.key));const heatRows=heat.characters.map(person=>`<div class="heatmap-name" title="${esc(person.name)}"><span>${esc(person.name)}</span><small>${person.chapterCount}章</small></div>${chapters.map(ch=>{const present=person.chapterKeys.includes(ch.key);return `<span class="heatmap-cell ${present?'present':''} part-${ch.partKey}" role="img" aria-label="${esc(person.name)} · ${esc(ch.title)} · ${present?'出现':'未出现'}" title="${esc(person.name)} · ${esc(ch.title)} · ${present?'出现':'未出现'}"></span>`}).join('')}`).join('');
 const heatmap=heatRows||'<div class="network-empty">当前范围没有可展示人物。</div>';const maxHeatColumns=Math.max(chapters.length,1);const heatHeader=`<div class="heatmap-corner">人物 / 章节</div>${chapters.map((ch,index)=>`<div class="heatmap-chapter" title="${esc(ch.part)} · ${esc(ch.title)}">${String(index+1).padStart(2,'0')}</div>`).join('')}`;
 const visibleParts=evolution.parts.filter(x=>state.visualPart==='全部'||x.partKey===state.visualPart);const maxTotal=Math.max(...visibleParts.map(x=>x.total),1);const colorByType=type=>`--event-color:${eventCatColor(type)}`;const legend=evolution.types.map(type=>`<span class="event-legend-item"><i style="${colorByType(type)}"></i>${esc(type)}</span>`).join('');const evolutionRows=visibleParts.map(part=>`<div class="evolution-row"><div class="evolution-label"><strong title="${esc(part.part)}">${esc(part.part)}</strong><span>${part.total}件事件</span></div><div class="evolution-track" title="${esc(part.part)} · ${part.total}件"><div class="evolution-fill" style="width:${part.total*100/maxTotal}%">${evolution.types.map(type=>`<span class="evolution-segment" style="width:${part.total?part.values[type]*100/part.total:0}%;background:${eventCatColor(type)}" title="${esc(type)} ${part.values[type]}件"></span>`).join('')}</div></div><div class="evolution-total">${part.total}</div></div>`).join('');
 const names=network.names;let selectedName=state.visualPerson&&network.byName[state.visualPerson]?state.visualPerson:(names[0]?.name||'');state.visualPerson=selectedName;const graph=network.byName[selectedName];const neighbors=(graph?.neighbors||[]).slice(0,12);const svgWidth=760,svgHeight=430,cx=svgWidth/2,cy=svgHeight/2,rx=290,ry=154;const positioned=neighbors.map((item,index)=>{const angle=-Math.PI/2+(Math.PI*2*index/Math.max(neighbors.length,1));return {...item,idx:index,x:Math.round(cx+Math.cos(angle)*rx),y:Math.round(cy+Math.sin(angle)*ry)}});const networkLinks=positioned.map(item=>{const t=item.idx%2?0.62:0.38;const lx=Math.round(cx+(item.x-cx)*t),ly=Math.round(cy+(item.y-cy)*t);const rel=item.relation||'';const showRel=rel&&!/同事件|推导/.test(rel);return `<line class="network-link ${item.direction==='in'?'incoming':''}" style="stroke:${relCatColor(item.category)}" x1="${cx}" y1="${cy}" x2="${item.x}" y2="${item.y}"><title>${esc(item.category)} · ${item.direction==='in'?'对方→我':item.direction==='out'?'我→对方':'双向'} · ${esc(item.relation)} · ${item.relationCount}条来源</title></line>${showRel?`<text class="network-edge-label" x="${lx}" y="${ly}">${esc(rel.length>12?rel.slice(0,12)+'...':rel)}</text>`:''}`}).join('');const networkNodes=positioned.map(item=>`<g><circle class="network-node" cx="${item.x}" cy="${item.y}" r="28"><title>${esc(item.name)} · ${item.chapterCount}章 · ${item.relationCount}条来源</title></circle><text class="network-label" x="${item.x}" y="${item.y+4}">${esc(item.name.length>6?item.name.slice(0,5)+'...':item.name)}</text></g>`).join('');const networkSvg=selectedName?`<svg class="network-svg" viewBox="0 0 ${svgWidth} ${svgHeight}" role="img" aria-label="${esc(selectedName)}的人物关系网络"><g>${networkLinks}</g><g><circle class="network-node center" cx="${cx}" cy="${cy}" r="42"><title>${esc(graph.center.name)} · ${graph.center.chapterCount}章 · ${graph.center.relationCount}条关系</title></circle><text class="network-label center" x="${cx}" y="${cy+4}">${esc(selectedName.length>7?selectedName.slice(0,6)+'...':selectedName)}</text></g><g>${networkNodes}</g></svg>`:'<div class="network-empty">当前范围没有可展示关系的人物。</div>';
 $('#visuals').innerHTML=`<div class="section-head"><div><h2>图谱：从章节分布到人物网络</h2><p>${esc(DATA.scopeLabel)} · 只展示高频人物、归一后的事件类别和核心人物邻域，保留原始数据的可读结构。</p></div><span class="status draft">图形用于发现线索</span></div><div class="visual-toolbar"><label for="visualPart">范围</label><select id="visualPart">${partOptions}</select><span class="visual-note">热力图按章节顺序排列；颜色和线型均有文字说明。</span></div><div class="visuals-stack"><section class="panel visuals-panel"><div class="section-head"><div><h3>一、人物出场轨迹</h3><p>纵轴为章节覆盖度最高的 24 位人物，横轴为当前范围内的章节序号；深色格表示该人物在该章有记录。</p></div><span class="visual-note">${heat.characters.length} 人 · ${chapters.length} 章</span></div><div class="heatmap-wrap"><div class="heatmap-grid" role="img" aria-label="人物出场矩阵：纵轴为覆盖度最高的 ${heat.characters.length} 位人物，横轴为 ${chapters.length} 章，深色格表示该人物在该章有记录；逐章明细见「人物」视图" style="--heatmap-columns:${maxHeatColumns}">${heatHeader}${heatmap}</div></div><div class="heatmap-legend"><span><i class="heatmap-key present"></i>有出场（深色 = 所属部次）</span><span><i class="heatmap-key absent"></i>本范围无出场</span><span class="legend-sep"></span><span class="legend-title">部次配色</span>${Object.entries(PART_COLORS).map(([k,v])=>`<span><i class="heatmap-key part" style="background:${v}"></i>${esc(PARTS[k]||k).split(' ')[0]}</span>`).join('')}<span class="legend-sep"></span><span>人物行按章节覆盖度排序</span></div></section><section class="panel visuals-panel"><div class="section-head"><div><h3>二、事件类型演变</h3><p>各分部共享同一尺度；条形长度代表该部事件总量，内部颜色表示归一后的事件类别。</p></div><span class="visual-note">${visibleParts.length} 个分部 · ${evolution.types.length} 类</span></div><div class="event-legend">${legend}</div><div class="evolution-list">${evolutionRows||'<div class="network-empty">当前范围没有事件。</div>'}</div></section><section class="panel visuals-panel"><div class="section-head"><div><h3>三、核心人物关系网络</h3><p>切换查看：中心人物邻域，或全书人物关系总图（力导向布局，点越大关系越多）。</p></div></div><div class="network-controls"><label for="netMode">关系视图</label><select id="netMode"><option value="ego" ${state.netMode==='ego'?'selected':''}>中心人物</option><option value="full" ${state.netMode==='full'?'selected':''}>全书人物图</option><option value="entity" ${state.netMode==='entity'?'selected':''}>全书实体图（含地点/机构/政权）</option></select><span class="muted grow" id="netModeNote">${state.netMode==='entity'?'实体图口径：节点=全部关系端点，不能读作「N 名人物」——人物图见上一项。':(state.netMode==='full'?'人物图口径（方案 A）：只保留人物↔人物关系，非人物端点不计入。':'')}</span></div><div id="egoNet" style="display:${state.netMode==='ego'?'block':'none'}"><div class="network-controls"><label for="visualPerson">中心人物</label><select id="visualPerson">${names.map(item=>`<option value="${esc(item.name)}" ${item.name===selectedName?'selected':''}>${esc(item.name)} · ${item.relationCount}条关系 · ${item.chapterCount}章</option>`).join('')}</select></div>${graph?`<div class="network-summary"><span>中心：<strong>${esc(graph.center.name)}</strong></span><span>覆盖 ${graph.center.chapterCount} 章</span><span>关系记录 ${graph.center.relationCount} 条</span><span>展示邻居 ${neighbors.length} 人</span></div><div class="cat-legend">${(DATA.relationCategories||[]).map(c=>`<span><i class="cat-dot" style="--cat:${relCatColor(c)};margin-right:4px"></i>${esc(c)}</span>`).join('')}</div>${networkSvg}`:'<div class="network-empty">暂无关系网络数据。</div>'}</div><div id="fullNet" style="display:${state.netMode==='ego'?'none':'block'}"><div class="network-summary" id="fullSummary"></div><canvas id="fullGraph" class="network-svg full-graph-canvas" role="img" aria-describedby="fullSummary" aria-label="关系网络图（渲染中）"></canvas><div id="fullTip" class="full-graph-tip-box"></div><div class="cat-legend" id="fullLegend"></div><p class="full-graph-tip">滚轮缩放 · 拖拽平移 · 点击节点高亮其邻域 · 点击空白复位</p></div></section></div>`;
 $('#visualPart').addEventListener('change',event=>{state.visualPart=event.target.value;renderVisuals()});$('#visualPerson').addEventListener('change',event=>{state.visualPerson=event.target.value;renderVisuals()});
const nmEl=$('#netMode');if(nmEl){nmEl.addEventListener('change',e=>{state.netMode=e.target.value;writeHash({view:'visuals',net:state.netMode==='ego'?'':state.netMode});const ego=$('#egoNet'),full=$('#fullNet');if(state.netMode!=='ego'){ego.style.display='none';full.style.display='block';fullSummaryHTML&&renderFullGraph()}else{ego.style.display='block';full.style.display='none';stopFullSim();}const note=$('#netModeNote');if(note)note.textContent=state.netMode==='entity'?'实体图口径：节点=全部关系端点，不能读作「N 名人物」——人物图见上一项。':(state.netMode==='full'?'人物图口径（方案 A）：只保留人物↔人物关系，非人物端点不计入。':'');});if(state.netMode!=='ego'){renderFullGraph()}}
}
function factionColor(tier){const palette=['#8d3025','#476b86','#527b5c','#b88b35','#6d688c','#a24b55','#3d7a7a','#9a6b2f','#7a5ca8','#4f7d3a','#b0466f','#356f9c','#8a6d2b','#5c7a3a','#9c5a3a'];let h=0;for(let i=0;i<tier.length;i++){h=(h*31+tier.charCodeAt(i))>>>0}return palette[h%palette.length]}
/* Phase 6 双模式图：同一个人物图/实体图切换入口。
   两种图口径不同——人物图只含人物（方案 A），实体图含地点/机构/政权/其他；
   因此统计文案、图例、悬浮提示都要按当前模式走，绝不能把实体数说成人物数。 */
const GRAPH_KIND_LABELS={person:'人物',place:'地点',org:'机构',regime:'政权',other:'其他'};
const GRAPH_KIND_COLORS={person:'#8d3025',place:'#476b86',org:'#527b5c',regime:'#b88b35',other:'#6d688c'};
const kindLabel=k=>GRAPH_KIND_LABELS[k]||'其他';
const isEntityMode=()=>state.netMode==='entity'&&!!DATA.relationGraphEntities;
// 注意：兜底必须回落到人物图（relationGraphFull），不能回落成 activeGraph() 自己——
// 那会变成无限自递归导致栈溢出，直接把图谱视图打挂。
const activeGraph=()=>isEntityMode()?DATA.relationGraphEntities:DATA.relationGraphFull;
const nodeColor=nd=>isEntityMode()&&nd.kind!=='person'?GRAPH_KIND_COLORS[nd.kind]||GRAPH_KIND_COLORS.other:factionColor(nd.faction||nd.tier||'');
const fullModeOption=(v,label)=>`<option value="${v}" ${state.netMode===v?'selected':''}>${label}</option>`;
let fullT={k:1,tx:0,ty:0};
function applyFullTransform(){if(fullCanvas)drawFull()}
function fgByName(n){if(!_fgCache){_fgCache={};(activeGraph().nodes||[]).forEach(x=>{_fgCache[x.name]=x})}return _fgCache[n]}
function drawFull(){
  const g=activeGraph();if(!g||!g.nodes||!g.nodes.length)return;
  const ctx=fullCtx;ctx.save();ctx.setTransform(fullDpr,0,0,fullDpr,0,0);ctx.clearRect(0,0,fullCssW,fullCssH);
  const k=fullT.k,tx=fullT.tx,ty=fullT.ty;const hl=fullHighlight;const inc=new Set();
  const S=fullSim?fullSim.nodes:null;
  if(hl){inc.add(hl);g.links.forEach(l=>{if(l.source===hl)inc.add(l.target);if(l.target===hl)inc.add(l.source)});}
  g.links.forEach(l=>{const a=S?S[fullSim.ix[l.source]]:fgByName(l.source);const b=S?S[fullSim.ix[l.target]]:fgByName(l.target);if(!a||!b)return;const ax=a.x*k+tx,ay=a.y*k+ty,bx=b.x*k+tx,by=b.y*k+ty;let op=0.5,w=Math.min(0.6+l.count*0.35,3.2);if(hl){const on=(l.source===hl||l.target===hl);op=on?0.95:0.05;w=on?Math.min(w+0.8,4):w;}ctx.strokeStyle=relCatColor(l.category);ctx.globalAlpha=op;ctx.lineWidth=w;ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(bx,by);ctx.stroke();});
  ctx.globalAlpha=1;
  g.nodes.forEach((nd,i)=>{const s=S?S[i]:nd;const x=s.x*k+tx,y=s.y*k+ty,r=Math.max(s.r*k,2.2);let op=1;if(hl){op=inc.has(nd.name)?1:0.12;}ctx.globalAlpha=op;ctx.fillStyle=nodeColor(nd);ctx.beginPath();ctx.arc(x,y,r,0,6.2832);ctx.fill();ctx.lineWidth=0.8;ctx.strokeStyle='#fffdf9';ctx.stroke();const wantLabel=nd.kind&&nd.kind!=='person'?true:nd.degree>=10;if(wantLabel&&(!hl||inc.has(nd.name))){ctx.globalAlpha=op;ctx.fillStyle='#443a32';ctx.font='11px "Microsoft YaHei","PingFang SC",sans-serif';ctx.textAlign='center';ctx.fillText(nd.name.length>6?nd.name.slice(0,6)+'…':nd.name,x,y-r-4);}});
  ctx.globalAlpha=1;ctx.restore();
}
/* 实时力模拟：网格加速斥力 + 弹簧 + 中心引力 + 微抖动（轻微飘动） */
let fullSim=null,fullReduceMotion=false,_fullBound=false,_fullResizeBound=false,_fgAbort=null;
function sizeFullCanvas(){if(!fullCanvas)return;const g=activeGraph();if(!g)return;const cssW=fullCanvas.parentElement.clientWidth||800;const cssH=Math.max(320,Math.min(cssW*(g.height/g.width),cssW*1.15));fullCssW=cssW;fullCssH=cssH;fullDpr=window.devicePixelRatio||1;fullCanvas.style.height=cssH+'px';fullCanvas.width=Math.round(cssW*fullDpr);fullCanvas.height=Math.round(cssH*fullDpr);fullCanvas.style.width=cssW+'px';const s=cssW/g.width;fullT={k:s,tx:0,ty:0};if(!_fullResizeBound){_fullResizeBound=true;let rt=null;window.addEventListener('resize',()=>{if(!fullCanvas)return;clearTimeout(rt);rt=setTimeout(()=>{sizeFullCanvas();drawFull();},120);});}}
function initFullSim(){const g=activeGraph();if(!g||!g.nodes||!g.nodes.length){fullSim=null;return;}const nodes=g.nodes.map(nd=>({name:nd.name,kind:nd.kind||'person',kindLabel:nd.kindLabel||'',x:nd.x,y:nd.y,vx:0,vy:0,r:nd.r,degree:nd.degree,faction:nd.faction,tier:nd.tier,role:nd.role,fixed:false}));const ix={};nodes.forEach((n,i)=>ix[n.name]=i);const links=g.links.map(l=>({a:ix[l.source],b:ix[l.target],category:l.category,count:l.count}));fullSim={nodes,ix,links,w:g.width,h:g.height,alpha:1,alphaTarget:0,raf:null,dragIdx:-1,reduced:fullReduceMotion};}
function fullStep(){const S=fullSim;if(!S)return;const N=S.nodes,n=N.length;const k=24,rep=160,spring=0.02,gravity=0.018,cx=S.w/2,cy=S.h/2,alpha=S.alpha;const thermal=S.reduced?0:0.22;const cell=k*4;const grid=new Map();for(let i=0;i<n;i++){const nd=N[i];const gx=Math.floor(nd.x/cell),gy=Math.floor(nd.y/cell);const key=gx+'|'+gy;let arr=grid.get(key);if(!arr){arr=[];grid.set(key,arr);}arr.push(i);}for(let i=0;i<n;i++){const a=N[i];if(a.fixed)continue;let fx=0,fy=0;const gx=Math.floor(a.x/cell),gy=Math.floor(a.y/cell);for(let ox=-1;ox<=1;ox++)for(let oy=-1;oy<=1;oy++){const arr=grid.get((gx+ox)+'|'+(gy+oy));if(!arr)continue;for(let q=0;q<arr.length;q++){const j=arr[q];if(j===i)continue;const b=N[j];let dx=a.x-b.x,dy=a.y-b.y;let d2=dx*dx+dy*dy;if(d2<1e-3){dx=Math.random()-0.5;dy=Math.random()-0.5;d2=dx*dx+dy*dy+1e-3;}const d=Math.sqrt(d2);const f=rep/d2;fx+=dx/d*f;fy+=dy/d*f;}}fx+=(cx-a.x)*gravity;fy+=(cy-a.y)*gravity;a._fx=fx;a._fy=fy;}for(let e=0;e<S.links.length;e++){const l=S.links[e];const a=N[l.a],b=N[l.b];if(a.fixed&&b.fixed)continue;let dx=b.x-a.x,dy=b.y-a.y;let d=Math.sqrt(dx*dx+dy*dy)+1e-6;const f=(d-k)*spring;const fx=dx/d*f,fy=dy/d*f;if(!a.fixed){a._fx+=fx;a._fy+=fy;}if(!b.fixed){b._fx-=fx;b._fy-=fy;}}const damp=0.85,maxStep=12;for(let i=0;i<n;i++){const a=N[i];if(a.fixed){a.vx=0;a.vy=0;continue;}const jx=thermal?(Math.random()-0.5)*thermal:0;const jy=thermal?(Math.random()-0.5)*thermal:0;a.vx=(a.vx+a._fx*alpha+jx)*damp;a.vy=(a.vy+a._fy*alpha+jy)*damp;const sp=Math.hypot(a.vx,a.vy);if(sp>maxStep){a.vx*=maxStep/sp;a.vy*=maxStep/sp;}a.x+=a.vx;a.y+=a.vy;}S.alpha+=(S.alphaTarget-S.alpha)*0.02;if(S.alpha<0)S.alpha=0;}
function fullLoop(){if(!fullSim)return;fullStep();drawFull();if(fullSim.alpha<0.02&&fullSim.dragIdx<0){const r=fullSim.raf;fullSim.raf=null;if(r)cancelAnimationFrame(r);return;}fullSim.raf=requestAnimationFrame(fullLoop);}
function startFullSim(){if(!fullSim)initFullSim();if(fullSim&&!fullSim.raf){fullSim.raf=requestAnimationFrame(fullLoop);}}
function stopFullSim(){if(fullSim&&fullSim.raf){cancelAnimationFrame(fullSim.raf);fullSim.raf=null;}}
/* 关系统计口径统一入口。两种图的数字含义不同，文案必须分开写：
   - 人物图（方案 A）：只统计「人物↔人物」关系，非人物端点被排除并如实标出；
   - 实体图：节点含地点/机构/政权/其他，只能说「实体 N 个」，绝不能说「N 名人物」。 */
function fullSummaryHTML(g){
  if(isEntityMode()){
    const k=g.stats.byKind||{};
    const parts=Object.keys(GRAPH_KIND_LABELS).filter(x=>k[x]).map(x=>`${GRAPH_KIND_LABELS[x]} ${k[x]}`);
    return `<span>实体关系图：<strong>${g.stats.nodes}</strong> 个实体 · <strong>${g.stats.edges}</strong> 条关系</span>`
      +`<span>其中人物 <strong>${g.stats.personNodes}</strong> 位，另有 ${g.stats.nonPersonNodes} 个非人物实体</span>`
      +`<span>孤立人物 ${g.stats.isolatedPersons}（指与该人物毫无人物间关系者，全书人物共 ${g.stats.bookPersons}）</span>`
      +(parts.length?`<span class="muted">${parts.join(' · ')}</span>`:'');
  }
  const pct=g.stats.persons?Math.round(g.stats.isolated*100/g.stats.persons):0;
  return `<span>人物关系图：<strong>${g.stats.nodes}</strong> / ${g.stats.persons} 人 · <strong>${g.stats.edges}</strong> 条人物关系</span>`
    +`<span>孤立人物 ${g.stats.isolated}（${pct}%，指无任何人物间关系）</span>`
    +(g.stats.excludedNonPerson?`<span class="muted">另有 ${g.stats.excludedNonPerson} 条关系含非人物端点，未计入人物关系图</span>`:'');
}
function renderFullGraph(){
  const g=activeGraph();const sum=document.getElementById('fullSummary'),legend=document.getElementById('fullLegend'),canvas=document.getElementById('fullGraph');
  if(!g||!g.nodes||!g.nodes.length){if(sum)sum.innerHTML='<span>当前范围没有可绘制的关系图。</span>';return;}
  fullReduceMotion=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  fullCanvas=canvas;fullCtx=canvas.getContext('2d');_fgCache=null;fullHighlight=null;
  sizeFullCanvas();
  const catLegend=(DATA.relationCategories||[]).map(c=>`<span><i class="cat-dot" style="--cat:${relCatColor(c)};margin-right:4px"></i>${esc(c)}</span>`).join('');
  // 实体图按节点类型着色，必须配类型图例，否则颜色无从解读
  if(isEntityMode()){
    const k=(g.stats&&g.stats.byKind)||{};
    const kinds=Object.keys(GRAPH_KIND_LABELS).filter(x=>k[x]).map(x=>`<span><i class="kind-dot" style="--kind:${GRAPH_KIND_COLORS[x]}"></i>${GRAPH_KIND_LABELS[x]} ${k[x]}</span>`).join('');
    legend.innerHTML=`<span class="legend-title">节点类型</span>${kinds}<span class="legend-sep"></span><span class="legend-title">关系类别（线色）</span>${catLegend}<span class="muted"> · 点大小=关系数 · 可拖拽节点</span>`;
  }else{
    legend.innerHTML=catLegend+`<span class="muted"> · 点大小=关系数，颜色=势力大类 · 可拖拽节点</span>`;
  }
  sum.innerHTML=fullSummaryHTML(g);
  /* 无障碍：canvas 本身没有可读内容，必须给出描述性替代文本，
     并指向下方的文本统计（完整逐条数据在「关系」视图里）。 */
  if(canvas)canvas.setAttribute('aria-label',isEntityMode()
    ?`全书实体关系图：${g.stats.nodes} 个实体、${g.stats.edges} 条关系，节点按类型着色；逐条关系见「关系」视图`
    :`全书人物关系图：${g.stats.nodes} 人、${g.stats.edges} 条人物关系，另有 ${g.stats.excludedNonPerson||0} 条含非人物端点的关系未计入；逐条关系见「关系」视图`);
  stopFullSim();            // 防止多次渲染叠加多个 rAF 循环（CPU 翻倍、收敛被加速）
  initFullSim();
  drawFull();
  // 按元素而非全局布尔绑定：innerHTML 重建后 canvas 是新元素，监听器必须重新挂
  if(canvas.dataset.fgBound!=='1'){setupFullInteractions(canvas);canvas.dataset.fgBound='1';}
  startFullSim();
}
function showFullNode(name){const g=activeGraph();const node=fgByName(name);if(!node)return;fullHighlight=name;const inc=new Set([name]);g.links.forEach(l=>{if(l.source===name)inc.add(l.target);if(l.target===name)inc.add(l.source)});const neigh=[...inc].filter(x=>x!==name);document.getElementById('fullSummary').innerHTML=`<span>已选：<strong>${esc(name)}</strong></span><span>${esc(node.faction||'势力待补')}</span><span>关系 ${node.degree} 条</span><span>邻域 ${neigh.length} ${isEntityMode()?'个实体':'人'}</span>`;drawFull();}
function resetFullHighlight(){fullHighlight=null;const g=activeGraph();if(g)document.getElementById('fullSummary').innerHTML=fullSummaryHTML(g);drawFull();}
function setupFullInteractions(canvas){
  // 用模块级 AbortController：画布被 innerHTML 替换后重新挂载时，先 abort 上一轮，
  // window 级监听器随信号一并注销。（挂在 canvas 上会随旧画布一起被丢弃，
  // 但 window 上的监听器不会，逐次累积 → 事件泄漏。）
  if(_fgAbort){try{_fgAbort.abort()}catch(_){}}
  _fgAbort=new AbortController();const __sg={signal:_fgAbort.signal};
  const hit=(mx,my)=>{const arr=fullSim?fullSim.nodes:activeGraph().nodes;let best=-1,bd=1e9;for(let i=0;i<arr.length;i++){const nd=arr[i];const sx=nd.x*fullT.k+fullT.tx,sy=nd.y*fullT.k+fullT.ty;const d=Math.hypot(sx-mx,sy-my);const rr=Math.max(nd.r*fullT.k,2.2)+6;if(d<rr&&d<bd){bd=d;best=i;}}return best;};
  let panning=false,lx=0,ly=0,moved=false,dragIdx=-1;
  canvas.addEventListener('wheel',e=>{e.preventDefault();const rect=canvas.getBoundingClientRect();const mx=e.clientX-rect.left,my=e.clientY-rect.top;const f=e.deltaY<0?1.12:1/1.12;const nk=Math.min(Math.max(fullT.k*f,0.15),14);const r=nk/fullT.k;fullT.tx=mx-(mx-fullT.tx)*r;fullT.ty=my-(my-fullT.ty)*r;fullT.k=nk;drawFull();},__sg);
  canvas.addEventListener('pointerdown',e=>{const rect=canvas.getBoundingClientRect();const idx=hit(e.clientX-rect.left,e.clientY-rect.top);moved=false;lx=e.clientX;ly=e.clientY;if(idx>=0){dragIdx=idx;if(fullSim){const nd=fullSim.nodes[idx];nd.fixed=true;fullSim.dragIdx=idx;fullSim.alpha=Math.max(fullSim.alpha,0.6);fullSim.alphaTarget=0.6;}startFullSim();canvas.classList.add('dragging');if(canvas.setPointerCapture)try{canvas.setPointerCapture(e.pointerId);}catch(_){}}else{panning=true;canvas.classList.add('dragging');}},__sg);
  window.addEventListener('pointerup',()=>{if(dragIdx>=0&&fullSim){const nd=fullSim.nodes[dragIdx];nd.fixed=false;fullSim.dragIdx=-1;fullSim.alphaTarget=0;fullSim.alpha=Math.max(fullSim.alpha,0.35);}dragIdx=-1;panning=false;canvas.classList.remove('dragging');},__sg);
  canvas.addEventListener('pointermove',e=>{const rect=canvas.getBoundingClientRect();const mx=e.clientX-rect.left,my=e.clientY-rect.top;
    if(dragIdx>=0){const dx=e.clientX-lx,dy=e.clientY-ly;if(Math.abs(dx)>3||Math.abs(dy)>3)moved=true;const nd=fullSim.nodes[dragIdx];nd.x=(mx-fullT.tx)/fullT.k;nd.y=(my-fullT.ty)/fullT.k;nd.vx=dx/fullT.k;nd.vy=dy/fullT.k;lx=e.clientX;ly=e.clientY;fullSim.alpha=Math.max(fullSim.alpha,0.6);return;}
    if(panning){const dx=e.clientX-lx,dy=e.clientY-ly;if(Math.abs(dx)>3||Math.abs(dy)>3)moved=true;fullT.tx+=dx;fullT.ty+=dy;lx=e.clientX;ly=e.clientY;drawFull();return;}
    const idx=hit(mx,my);const tip=document.getElementById('fullTip');if(idx>=0){const nd=(fullSim?fullSim.nodes:fgByName(activeGraph().nodes[idx].name));canvas.style.cursor='grab';tip.style.display='block';tip.style.left=e.clientX+'px';tip.style.top=e.clientY+'px';tip.textContent=`${(nd.kind&&nd.kind!=='person')?'【'+kindLabel(nd.kind)+'】':''}${nd.name}${nd.faction?' · '+nd.faction:''}${nd.role&&nd.role!==nd.faction?' · '+nd.role:''} · ${nd.degree}条关系`;}else{canvas.style.cursor='grab';tip.style.display='none';}},__sg);
  canvas.addEventListener('click',e=>{if(moved){moved=false;return;}const rect=canvas.getBoundingClientRect();const idx=hit(e.clientX-rect.left,e.clientY-rect.top);if(idx>=0){const name=(fullSim?fullSim.nodes[idx].name:activeGraph().nodes[idx].name);showFullNode(name);}else resetFullHighlight();},__sg);
  // 指针离开画布时收起提示框，避免提示常驻挡住点击
  canvas.addEventListener('pointerleave',()=>{const tp=document.getElementById('fullTip');if(tp)tp.style.display='none';},__sg);
}
let fullCanvas=null,fullCtx=null,fullDpr=1,fullCssW=0,fullCssH=0,fullHighlight=null,_fgCache=null;
/* mentionedAs 里同时装了两样东西：真别称（塔山/两广/延平府）与说明片段（洪承畴籍贯、
   袁崇焕凌迟刑场）。构建期已拆成 altNames / mentionContext 两个字段，这里分别渲染——
   原先统一挂「别称：」会把「今辽宁兴城，'山'字型城墙，宁远之战主战场」当成别称列出来。*/
function mentionMeta(item){
  const alt=item.altNames||[],ctx=item.mentionContext||[];
  let s='';
  if(alt.length)s+=`<br>别称：${esc(alt.join('、'))}`;
  if(ctx.length)s+=`<br>书中提及：${esc(ctx.slice(0,3).join(' · '))}${ctx.length>3?` 等 ${ctx.length} 处`:''}`;
  return s;
}
function mentionBlock(item){
  const alt=item.altNames||[],ctx=item.mentionContext||[];
  return `<div class="detail-block"><strong>别称</strong><p>${esc(alt.join('、')||'无')}</p></div>`
    +`<div class="detail-block"><strong>书中提及（${ctx.length}）</strong><p>${esc(ctx.join(' · ')||'—')}</p></div>`;
}
function locationCard(item){const coords=item.lat!=null?`${Number(item.lat).toFixed(2)}, ${Number(item.lng).toFixed(2)}`:'未定位';return `<article class="location-card"><div class="card-head"><div><span class="card-title">${esc(item.ancient)}</span> <span class="tag">${esc(item.trace)}</span></div><span class="status ${item.status==='已定位'?'':'draft'}">${esc(shortStatus(item.status))}</span></div><div class="meta">今址：${esc(item.modern)}${mentionMeta(item)}</div><div class="meta">坐标：${esc(coords)} · ${esc(item.region)}</div>${(item.directEvents||[]).length?`<div class="meta"><b>直接关联事件：</b><ul class="event-list">${(item.directEvents||[]).slice(0,6).map(x=>`<li><button class="link-button" data-event-name="${esc(x)}">${esc(x)}</button></li>`).join('')}</ul></div>`:`<div class="meta">当前章节仅提及，未确认具体事件落点。</div>`}${item.relatedEventCount?`<div class="meta muted">同章另提及 ${item.relatedEventCount} 件事件（未直接落点于本地点）。</div>`:''}<div class="source-row">${chapterChips(item.chapters)}<button class="action" data-location-id="${item.id}">详情</button></div></article>`}
function bindPaging(root,callback){root.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{if(!b.disabled){callback(b.dataset.page==='next'?1:-1)}}))}
function renderLocations(){
 const all=DATA.locations.filter(x=>(!state.locQuery||`${x.ancient} ${x.modern} ${x.region} ${(x.mentionedAs||[]).join(' ')}`.toLowerCase().includes(state.locQuery.toLowerCase()))&&(!state.locRegion||state.locRegion==='全部区域'||x.region===state.locRegion));
 const body=state.locMode==='index'?`<div class="data-grid">${slicePage(all,state.locPage).map(locationCard).join('')||'<div class="empty">没有匹配地点</div>'}</div>${pager(state.locPage,all.length)}`:`<div class="chapter-list">${DATA.chapterLocations.slice((state.chapterPage-1)*12,state.chapterPage*12).map(ch=>`<article class="chapter-block"><h3>${esc(ch.title)} <span class="muted">${esc(ch.part)}</span></h3>${ch.items.map(item=>`<div class="chapter-place"><strong>${esc(item.ancient)}</strong><span>${esc(item.modern)} · <span class="status ${item.status==='已定位'?'':'draft'}">${esc(shortStatus(item.status))}</span>${(item.directEvents||[]).length?`<br><span class="muted">${(item.directEvents||[]).slice(0,4).map(esc).join(' · ')}</span>`:''}</span></div>`).join('')}</article>`).join('')}</div>${pager(state.chapterPage,DATA.chapterLocations.length,12)}`;
 $('#locations').innerHTML=`<div class="section-head"><div><h2>地点索引</h2><p>${metrics.locations} 个地点实体，${metrics.locatedLocations} 个已定位；直接关联事件与同章提及分开显示。</p></div></div><div class="panel"><div class="subnav"><button data-loc-mode="index" class="${state.locMode==='index'?'active':''}">地点索引</button><button data-loc-mode="chapter" class="${state.locMode==='chapter'?'active':''}">按章节</button></div>${state.locMode==='index'?`<div class="toolbar"><label>搜索</label><input class="search" id="locQuery" value="${esc(state.locQuery)}" placeholder="古名、今址或区域"><label>区域</label><select id="locRegion"><option>全部区域</option>${[...new Set(DATA.locations.map(x=>x.region))].filter(Boolean).sort().map(x=>`<option ${x===state.locRegion?'selected':''}>${esc(x)}</option>`).join('')}</select></div>`:''}${body}</div>`;
 bindSearch('#locQuery','locQuery',()=>{state.locPage=1;renderLocations()});$('#locRegion').addEventListener('change',e=>{state.locRegion=e.target.value;state.locPage=1;renderLocations()});document.querySelectorAll('[data-loc-mode]').forEach(b=>b.addEventListener('click',()=>{state.locMode=b.dataset.locMode;renderLocations()}));
 const root=$('#locations');bindPaging(root,delta=>{if(state.locMode==='index')state.locPage+=delta;else state.chapterPage+=delta;renderLocations()});
 root.querySelectorAll('[data-location-id]').forEach(b=>b.addEventListener('click',()=>{const x=DATA.locations.find(y=>y.id===b.dataset.locationId);if(!x)return;openDetail(x.ancient,locationDetailHTML(x,'event'));bindEventNameClicks()}));
 root.querySelectorAll('[data-event-name]').forEach(b=>b.addEventListener('click',()=>{const event=DATA.events.find(x=>x.name===b.dataset.eventName);if(event)showEvent(event)}));
}
function showEvent(event){openDetail(event.name,`<div class="detail-grid">${insightBlock('event',event.name)}<div class="detail-block"><strong>时间</strong><p>${esc(event.year||'年份待考')}${event.year_source?` <span class="src-tag">${event.year_approx?'约·':''}来源：${esc(event.year_source)}</span>`:''}${event.year_note?` <span class="src-note">（${esc(event.year_note)}）</span>`:''}</p></div><div class="detail-block"><strong>类别</strong><p>${catBadge(event.category,eventCatColor(event.category))}</p></div><div class="detail-block"><strong>原类型</strong><p>${esc(event.type)}</p></div><div class="detail-block"><strong>地点</strong><p>${eventLocationChips(event)}</p></div><div class="detail-block"><strong>参与者</strong><p>${esc(event.participants.join('、')||'未标注')}</p></div><div class="detail-block detail-wide"><strong>来源章节</strong><div class="source-row">${chapterChips(event.sources)}</div></div></div>`)}
function locationDetailHTML(x, evtAttr){
  const evs=(x.directEvents||[]).map(n=>DATA.events.find(e=>e.name===n)).filter(Boolean);
  const people=[...new Set(evs.flatMap(e=>e.participants||[]))];
  const eventsHtml=evs.length?`<ul class="event-list">${evs.map(e=>`<li><button class="link-button" data-${evtAttr}="${esc(e.name)}">${esc(e.name)}</button> · ${esc(e.year||'年份待考')}</li>`).join('')}</ul>`:`<p class="muted">当前范围仅提及，书中未确认具体事件落点。</p>`;
  const relEvs=x.relatedEvents||[];
  const relatedHtml=relEvs.length?`<div class="meta"><b>同章上下文事件（${relEvs.length}）</b></div><ul class="event-list">${relEvs.slice(0,15).map(n=>`<li><button class="link-button" data-${evtAttr}="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul><p class="muted">（同章提及，未直接落点于本地点；可作圣地巡礼上下文）</p>`:`<p class="muted">同章亦无其它事件记录。</p>`;
  const relPeople=x.relatedPeople||[];
  const ph=people.length?esc(people.slice(0,15).join('、')):(relPeople.length?esc(relPeople.slice(0,15).join('、')):'无（或未标注）');
  const phNote=people.length?'':'<span class="muted">（来自同章上下文事件）</span>';
  return `<div class="detail-grid">${insightBlock('place',x.ancient)}<div class="detail-block"><strong>今址</strong><p>${esc(x.modern)}</p></div><div class="detail-block"><strong>书中身份</strong><p>${esc(x.trace)}</p></div>${mentionBlock(x)}<div class="detail-block"><strong>坐标</strong><p>${x.lat==null?'未定位':`${x.lat}, ${x.lng}`}</p></div><div class="detail-block detail-wide"><strong>书中直接关联事件（${evs.length}）</strong>${eventsHtml}${relatedHtml}</div><div class="detail-block detail-wide"><strong>书中涉及人物 ${phNote}</strong><p>${ph}</p></div><div class="detail-block detail-wide"><strong>来源章节</strong><div class="source-row">${chapterChips(x.chapters)}</div></div><div class="detail-block detail-wide"><strong>核验备注</strong><p>${esc(x.note||'暂无')}</p></div></div>`;
}
function bindEventNameClicks(){const dlg=$('#detailDialog');if(!dlg)return;dlg.querySelectorAll('[data-event-name],[data-loc-event]').forEach(b=>b.addEventListener('click',()=>{const nm=b.dataset.eventName||b.dataset.locEvent;const ev=DATA.events.find(e=>e.name===nm);if(ev)showEvent(ev)}))}
function showLocation(x){// 非地图视图（例如从事件详情、地点卡片点入）时，dock 位于隐藏面板内，内容看不见；改用弹窗展示
  if(state.view!=='map'){openDetail(x.ancient,locationDetailHTML(x,'event'));bindEventNameClicks();return;}
  const html=locationDetailHTML(x,'loc');const dock=$('#locDock');dock.innerHTML=`<div class="dock-head"><h3>${esc(x.ancient)}</h3><button class="dock-close" id="locDockClose">关闭</button></div>${html}`;dock.hidden=false;const closeDock=()=>{dock.hidden=true;if(mapInstance)setTimeout(()=>mapInstance.invalidateSize(),60)};$('#locDockClose').addEventListener('click',closeDock);dock.querySelectorAll('[data-loc-event]').forEach(b=>b.addEventListener('click',()=>{const ev=DATA.events.find(e=>e.name===b.dataset.locEvent);if(ev)showEvent(ev)}));if(mapInstance)setTimeout(()=>mapInstance.invalidateSize(),60)}
let mapInstance=null,voyageMapInstance=null;
// Leaflet 按需懒加载：仅在打开地图视图时从 CDN 注入，避免首屏被 unpkg 阻塞。
// 加载失败则保持 SVG 点位图兜底（renderMap/renderVoyage 的 window.L 缺失分支）。
let _leafletPromise=null;
function loadLeaflet(){
  if(window.L)return Promise.resolve();
  if(_leafletPromise)return _leafletPromise;
  _leafletPromise=new Promise((resolve,reject)=>{
    const css=document.createElement('link');css.rel='stylesheet';
    css.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(css);
    const s=document.createElement('script');
    s.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    s.onload=()=>resolve();s.onerror=()=>{_leafletPromise=null;reject(new Error('leaflet load failed'));};
    document.head.appendChild(s);
  });
  return _leafletPromise;
}
function renderMap(){
  const mode=state.mapMode;
  const pp=$('#pilgrimPanel'),vp=$('#voyagePanel');
  if(pp)pp.style.display=mode==='pilgrim'?'':'none';
  if(vp)vp.style.display=mode==='voyage'?'':'none';
  if(mode==='voyage'){renderVoyage();return;}
  const locations=DATA.locations.filter(x=>x.lat!=null&&x.lng!=null);
  const showMarkers=state.showMarkers;
  $('#mapNote').textContent=`已定位 ${locations.length}/${DATA.locations.length} 个地点。${window.L?'地图瓦片来自 Esri/OSM，需联网加载。':'当前为离线点位图，地图组件按需加载。'}`;
  const box=$('#mapBox');
  if(mapInstance){mapInstance.remove();mapInstance=null}
  box.innerHTML='';
  $('#mapNote').textContent=`已定位 ${locations.length}/${DATA.locations.length} 个地点。地图瓦片来自 Esri（备用 OSM），需联网加载。`;
  const drawLeaflet=()=>{
    const map=L.map(box).setView([34.5,113],4);mapInstance=map;
    makeTiles().addTo(map);
    if(showMarkers){locations.forEach(x=>{const m=L.circleMarker([x.lat,x.lng],{radius:6,color:'#8d3025',fillColor:'#b94a37',fillOpacity:.85}).addTo(map);m.bindTooltip(esc(x.ancient));m.on('click',()=>showLocation(x))})}
    setTimeout(()=>map.invalidateSize(),100);
  };
  const drawSvg=()=>{
    const proj=x=>{const px=Math.max(30,Math.min(970,(x.lng-73)/62*940)),py=Math.max(30,Math.min(490,(54-x.lat)/36*460));return[px,py]};
    const dots=showMarkers?locations.map(x=>{const[px,py]=proj(x);return `<circle cx="${px}" cy="${py}" r="5" fill="#8d3025" data-loc-ancient="${esc(x.ancient)}" style="cursor:pointer"><title>${esc(x.ancient)} · ${esc(x.modern)}（点击查看书中介绍）</title></circle>`}).join(''):'';
    box.innerHTML=`<svg class="fallback-map" viewBox="0 0 1000 520" role="img" aria-label="地点坐标图"><rect width="1000" height="520" fill="#e6eee7"/>${dots}</svg>`;
    box.querySelectorAll('[data-loc-ancient]').forEach(c=>c.addEventListener('click',()=>{const x=DATA.locations.find(y=>y.ancient===c.dataset.locAncient);if(x)showLocation(x)}));
  };
  if(window.L){drawLeaflet();dismissFail('leaflet');}
  else{
    drawSvg();   // 先立即显示离线点位图，不阻塞；Leaflet 就绪后再升级
    loadLeaflet().then(()=>{dismissFail('leaflet');if(state.view==='map'&&state.mapMode==='pilgrim'&&mapInstance==null)drawLeaflet();})
      .catch(()=>{
        $('#mapNote').textContent=`已定位 ${locations.length}/${DATA.locations.length} 个地点。当前为离线点位图（地图组件加载失败，可重试）。`;
        failBar('leaflet','地图组件（Leaflet）加载失败，当前显示离线点位图（点位与点击详情不受影响）。',{level:'warn',
          retry:()=>{_leafletPromise=null;renderMap();}});
      });
  }
}
function renderVoyage(){
  const v=DATA.voyages;const box=$('#voyageBox');
  if(voyageMapInstance){voyageMapInstance.remove();voyageMapInstance=null}
  box.innerHTML='';
  if(!v||!v.points||v.points.length<2){$('#voyageNote').textContent='暂无航线数据（停靠点坐标待补）';return;}
  const pts=v.points;
  $('#voyageNote').textContent=`${esc(v.name)} · ${pts.length} 个停靠点${v.illustrative?'（坐标为示意，需史料核验）':''}`;
  const drawLeaflet=()=>{
    box.innerHTML='';
    const map=L.map(box);voyageMapInstance=map;
    makeTiles().addTo(map);
    const latlngs=pts.map(p=>[p.lat,p.lng]);
    L.polyline(latlngs,{color:'#b88b35',weight:3,dashArray:'7 6',opacity:.9}).addTo(map).bindPopup(`<b>${esc(v.name)}</b><br>${esc(v.note||'')}`);
    pts.forEach((p,i)=>{const m=L.circleMarker([p.lat,p.lng],{radius:8,color:'#8a6a1f',fillColor:'#e8c872',fillOpacity:.95,weight:2}).addTo(map);m.bindPopup(`<b>${i+1}. ${esc(p.name)}</b><br>${esc(p.desc||'')}`);m.bindTooltip(String(i+1),{permanent:true,direction:'top',className:'voyage-num',offset:[0,-9]});m.on('click',()=>showVoyageStop(p,i))});
    map.fitBounds(latlngs,{padding:[40,40]});
    setTimeout(()=>map.invalidateSize(),100);
  };
  const drawSvg=()=>{
    const lats=pts.map(p=>p.lat),lngs=pts.map(p=>p.lng);
    const minLat=Math.min(...lats),maxLat=Math.max(...lats),minLng=Math.min(...lngs),maxLng=Math.max(...lngs);
    const proj=p=>{const px=30+(p.lng-minLng)/(maxLng-minLng||1)*940,py=490-(p.lat-minLat)/(maxLat-minLat||1)*460;return[px,py]};
    const route=`<polyline points="${pts.map(p=>proj(p).join(',')).join(' ')}" fill="none" stroke="#b88b35" stroke-width="2" stroke-dasharray="6 5"/>`+pts.map((p,i)=>{const[px,py]=proj(p);return `<circle cx="${px}" cy="${py}" r="7" fill="#e8c872" stroke="#8a6a1f" stroke-width="2" data-stop="${i}"><title>${i+1}. ${esc(p.name)}</title></circle><text x="${px}" y="${py+3}" text-anchor="middle" font-size="9" fill="#5f4a14" font-weight="bold">${i+1}</text>`}).join('');
    box.innerHTML=`<svg class="fallback-map" viewBox="0 0 1000 520" role="img" aria-label="郑和航线图"><rect width="1000" height="520" fill="#e6eee7"/>${route}</svg>`;
    box.querySelectorAll('circle[data-stop]').forEach(c=>c.addEventListener('click',()=>{const k=Number(c.dataset.stop);if(pts[k])showVoyageStop(pts[k],k)}));
  };
  if(window.L){drawLeaflet();dismissFail('leaflet');}
  else{
    drawSvg();
    loadLeaflet().then(()=>{dismissFail('leaflet');if(state.view==='map'&&state.mapMode==='voyage'&&voyageMapInstance==null)drawLeaflet();})
      .catch(()=>{
        $('#voyageNote').textContent=`${esc(v.name)} · ${pts.length} 个停靠点（地图组件加载失败，当前为离线航线示意图）。`;
        failBar('leaflet','地图组件（Leaflet）加载失败，航线以离线示意图显示（停靠点详情不受影响）。',{level:'warn',
          retry:()=>{_leafletPromise=null;renderVoyage();}});
      });
  }
}
function showVoyageStop(p,i){const dock=$('#voyageDock');const evs=p.events||[];dock.innerHTML=`<div class="dock-head"><h3>${i+1}. ${esc(p.name)}</h3><button class="dock-close" id="voyageDockClose">关闭</button></div><div class="detail-grid"><div class="detail-block detail-wide"><strong>停靠序号</strong><p>第 ${i+1} 站 / 共 ${DATA.voyages.points.length} 站</p></div><div class="detail-block detail-wide"><strong>书中描述</strong><p>${esc(p.desc||'（书中仅提及，未详述）')}</p></div><div class="detail-block"><strong>坐标</strong><p>${Number(p.lat).toFixed(2)}, ${Number(p.lng).toFixed(2)}</p></div><div class="detail-block"><strong>核验</strong><p class="muted">${DATA.voyages.illustrative?'坐标为示意，需史料核验':'坐标已核验'}</p></div><div class="detail-block detail-wide"><strong>书中相关事件</strong>${evs.length?`<ul class="event-list">${evs.map(e=>`<li><button class="link-button" data-event-id="${e.id}">${esc(e.name)}</button>${e.year?` <span class="muted">${esc(String(e.year))}</span>`:''}</li>`).join('')}</ul>${p.eventsDirect?'':'<p class="muted">书中未直接提及此停靠点，以上为本航线同章大事。</p>'}`:'<p class="muted">暂无</p>'}</div></div>`;dock.hidden=false;$('#voyageDockClose').addEventListener('click',()=>{dock.hidden=true});dock.querySelectorAll('[data-event-id]').forEach(b=>b.addEventListener('click',()=>{const x=DATA.events.find(y=>y.id===b.dataset.eventId);if(x)showEvent(x)}))}

function renderCharacters(){
 const factions=[...new Set(DATA.characters.map(x=>x.faction).filter(Boolean))].sort();const list=DATA.characters.filter(x=>(!state.charPart||x.chapters.some(k=>k.startsWith(state.charPart+'-')))&&(!state.charFaction||state.charFaction==='全部势力'||x.faction===state.charFaction)&&(!state.charQuery||x.name.toLowerCase().includes(state.charQuery.toLowerCase())||(x.aliases||[]).some(a=>a.toLowerCase().includes(state.charQuery.toLowerCase())))&&(state.charMinor||state.charQuery.trim()||x.chapters.length>1));const page=slicePage(list,state.charPage);$('#characters').innerHTML=`<div class="section-head"><div><h2>人物索引</h2><p>${metrics.characters} 个角色实体；默认按章节覆盖度排序，关系完整保留在详情中。</p></div></div><div class="panel"><div class="toolbar"><label>部次</label><select id="charPart"><option value="">全部七部</option>${Object.entries(PARTS).map(([k,v])=>`<option value="${k}" ${state.charPart===k?'selected':''}>${esc(v)}</option>`).join('')}</select><label>势力</label><select id="charFaction"><option>全部势力</option>${factions.map(x=>`<option ${state.charFaction===x?'selected':''}>${esc(x)}</option>`).join('')}</select><input class="search grow" id="charQuery" value="${esc(state.charQuery)}" placeholder="姓名或别名（如 崇祯、王阳明）"><button class="action" id="charReset">重置</button></div><div class="character-toolbar"><button class="mode active" data-char-mode="screen">屏幕卡</button><button class="mode" data-char-mode="front">打印正面</button><button class="mode" data-char-mode="back">打印背面</button><label style="display:inline-flex;gap:5px;align-items:center;color:var(--muted)">卡面</label><select id="cardTheme"><option value="thm-ink" ${state.cardTheme==='thm-ink'?'selected':''}>墨玉</option><option value="thm-paper" ${state.cardTheme==='thm-paper'?'selected':''}>宣纸</option><option value="thm-cinnabar" ${state.cardTheme==='thm-cinnabar'?'selected':''}>朱砂</option></select><label><input type="checkbox" id="charMinor" ${state.charMinor?'checked':''}> 显示仅出场一章的人物</label><span class="muted" id="charCount">显示 ${page.length} / ${list.length} · 次要(仅1章) ${DATA.characters.filter(x=>x.chapters.length<=1).length} 人${state.charMinor||state.charQuery.trim()?'':'（已折叠）'}</span></div><div id="charScreen" class="character-grid">${page.map(characterCard).join('')||'<div class="empty">没有匹配人物</div>'}</div><div id="printGuide" class="print-guide" style="display:none">当前筛选结果共 ${list.length} 张；打印页只在选择打印模式时生成。</div><div id="printArea" class="print-area"></div>${pager(state.charPage,list.length)}</div>`;
 $('#charPart').addEventListener('change',e=>{state.charPart=e.target.value;state.charPage=1;renderCharacters()});$('#charFaction').addEventListener('change',e=>{state.charFaction=e.target.value;state.charPage=1;renderCharacters()});bindSearch('#charQuery','charQuery',()=>{state.charPage=1;renderCharacters()});$('#charReset').addEventListener('click',()=>{state.charPart='';state.charFaction='全部势力';state.charQuery='';state.charMinor=false;state.charPage=1;renderCharacters()});
 $('#charMinor').addEventListener('change',e=>{state.charMinor=e.target.checked;state.charPage=1;renderCharacters()});
$('#cardTheme').addEventListener('change',e=>{state.cardTheme=e.target.value;renderCharacters()});
 const root=$('#characters');bindPaging(root,delta=>{state.charPage+=delta;renderCharacters()});root.querySelectorAll('[data-char-mode]').forEach(b=>b.addEventListener('click',()=>{root.querySelectorAll('[data-char-mode]').forEach(x=>x.classList.remove('active'));b.classList.add('active');if(b.dataset.charMode==='screen'){root.querySelector('#charScreen').style.display='grid';root.querySelector('#printGuide').style.display='none';root.querySelector('#printArea').style.display='none'}else{root.querySelector('#charScreen').style.display='none';root.querySelector('#printGuide').style.display='block';root.querySelector('#printArea').style.display='block';renderPrint(b.dataset.charMode,list)}}));root.querySelectorAll('[data-char-detail]').forEach(b=>b.addEventListener('click',()=>{const x=DATA.characters.find(y=>y.name===b.dataset.charDetail);showPerson(x.name)}));
}
/* 卡面字段（P2-03）：优先读 Python 端一次性解析好的 profile，
   不再用正则从展示串里猜字段含义。
   profile 契约见 src/core/faction_profile.py：
     label 势力标签 / origin 籍贯 / note 括号备注 / office 官职 / jinshi_year 科举年份
   只有在 profile 缺失（例如旧 payload）时才回退到原先的字符串清洗逻辑。 */
function cleanCardFields(x){
 const p=x&&x.profile;
 if(p&&typeof p==='object'&&p.label!==undefined){
  return{
   faction:p.label||x.faction||'势力待补',
   role:(x.role||'').trim(),
   birth:p.origin||'',
   extra:p.note||'',
   office:(p.office||[]).join('、'),
   jinshi:p.jinshi_year||null,
   dynasty:p.dynasty||'',
   raw:p.raw||''
  };
 }
 let faction=(x.faction||'').trim(),extra='';
 const m=faction.match(/（([^（）]*)）\s*$/);
 if(m){extra=m[1];faction=faction.slice(0,m.index).trim()}
 faction=faction.replace(/^明朝\s*[·・:：]?\s*/,'').replace(/^明\s*[·・]\s*/,'').trim();
 let birth=(x.birth||'').trim();
 if(!birth&&extra){const bp=extra.match(/([^，,、]+人)/);if(bp)birth=bp[1]}
 return{faction:faction||x.faction||'势力待补',role:(x.role||'').trim(),birth,extra,office:'',jinshi:null,dynasty:'',raw:x.faction||''};
}
function characterCard(x){
 const F=cleanCardFields(x);
 const evLine=x.events.length?esc(x.events.slice(0,3).join('、')):`<span class="muted">${esc((x.contextEvents||[]).slice(0,3).join('、')||'无')}</span><span class="src-note">（同章提及）</span>`;
 const _q=(DATA.quotes||{})[x.name];
 const row=(k,v)=>`<div class="pcb-row"><dt>${k}</dt><dd>${v||'<span class="muted">未标注</span>'}</dd></div>`;
 return `<article class="character-card ${state.cardTheme||'thm-ink'}" data-char="${esc(x.name)}"><div class="inner">
  <div class="face front">
   <div class="pc-head"><span class="pc-faction">${esc(F.faction)}</span><span class="pc-seal" aria-hidden="true">明</span></div>
   <h3 class="pc-name">${esc(x.name)}</h3>
   <div class="pc-rule"></div>
   <p class="pc-quote">${esc(x.summary||'')}</p>
   <div class="pc-foot"><span class="pc-chapters">见 ${x.chapters.length} 章</span><span class="card-actions"><button data-flip>翻面</button><button data-char-detail="${esc(x.name)}">详情</button></span></div>
  </div>
  <div class="face back" inert>
   <div class="pcb-head"><h3>${esc(x.name)}</h3><span class="pcb-life">${esc(x.life||'生卒待考')}</span></div>
   <dl class="pcb-list">
    ${row('身份',esc(F.role))}
        ${row('籍贯',esc(F.birth))}
    ${F.extra&&F.extra!==F.birth?row('出身',esc(F.extra)):''}
    ${row('状态',esc(x.status))}
    ${row('事件',evLine)}
    ${_q?row('语录',`「${esc(_q)}」`):''}
   </dl>
   <div class="pcb-foot"><span class="pc-chapters">见 ${x.chapters.length} 章</span><span class="card-actions"><button data-flip>翻面</button><button data-char-detail="${esc(x.name)}">详情</button></span></div>
  </div>
 </div></article>`}
function renderPrint(kind,list){
  const theme=state.cardTheme||'thm-ink';
  const pages=[];
  for(let i=0;i<list.length;i+=9){
    const cards=list.slice(i,i+9).map(x=>{
      const F=cleanCardFields(x);
      if(kind==='front'){
        return `<article class="character-card print-card front ${theme}">
          <div class="pc-head"><span class="pc-faction">${esc(F.faction)}</span><span class="pc-seal" aria-hidden="true">明</span></div>
          <h3 class="pc-name">${esc(x.name)}</h3>
          <div class="pc-rule"></div>
          <p class="pc-quote">${esc(x.summary||'')}</p>
          <div class="pc-foot"><span class="pc-chapters">见 ${x.chapters.length} 章</span></div>
        </article>`;
      }
      const evLine=x.events.length?esc(x.events.slice(0,3).join('、')):`<span class="muted">${esc((x.contextEvents||[]).slice(0,3).join('、')||'无')}</span><span class="src-note">（同章提及）</span>`;
      const _q=(DATA.quotes||{})[x.name];
      const row=(k,v)=>`<div class="pcb-row"><dt>${k}</dt><dd>${v||'<span class="muted">未标注</span>'}</dd></div>`;
      return `<article class="character-card print-card back ${theme}">
        <div class="pcb-head"><h3>${esc(x.name)}</h3><span class="pcb-life">${esc(x.life||'生卒待考')}</span></div>
        <dl class="pcb-list">
          ${row('身份',esc(F.role))}
                    ${row('籍贯',esc(F.birth))}
          ${F.extra&&F.extra!==F.birth?row('出身',esc(F.extra)):''}
          ${row('状态',esc(x.status))}
          ${row('事件',evLine)}
          ${_q?row('语录',`「${esc(_q)}」`):''}
        </dl>
        <div class="pcb-foot"><span class="pc-chapters">见 ${x.chapters.length} 章</span></div>
      </article>`;
    }).join('');
    pages.push(`<div class="print-page"><div class="print-grid">${cards}</div></div>`);
  }
  $('#printArea').innerHTML=pages.join('');
}
function renderEvents(){const types=[...new Set(DATA.events.map(x=>x.type))].sort();const cats=DATA.eventCategories||[];const counts={};DATA.events.forEach(x=>{counts[x.category]=(counts[x.category]||0)+1});const list=DATA.events.filter(x=>(state.eventCategory==='全部类别'||x.category===state.eventCategory)&&(!state.eventQuery||matchesQuery(`${x.name} ${x.location} ${x.participants.join(' ')}`,state.eventQuery)));const page=slicePage(list,state.eventPage);$('#events').innerHTML=`<div class="section-head"><div><h2>事件索引</h2><p>${metrics.events} 件事件；年份待考的 ${metrics.unknownEvents} 件仍保留在索引中。</p></div></div><div class="panel"><div class="toolbar"><label>类别</label><select id="eventCategory"><option value="全部类别" ${state.eventCategory==='全部类别'?'selected':''}>全部类别（${DATA.events.length}）</option>${cats.map(c=>`<option value="${esc(c)}" ${state.eventCategory===c?'selected':''}>${esc(c)}（${counts[c]||0}）</option>`).join('')}</select><input class="search grow" id="eventQuery" value="${esc(state.eventQuery)}" placeholder="搜索事件、地点或参与者"></div><div class="table-wrap"><table class="data-table"><thead><tr><th>事件</th><th>年份</th><th>类别</th><th>原类型</th><th>地点</th><th>参与者</th><th>来源</th></tr></thead><tbody>${page.map(x=>`<tr><td><button class="link-button" data-event-id="${x.id}">${esc(x.name)}</button></td><td>${esc(x.year||'待考')}</td><td>${catBadge(x.category,eventCatColor(x.category))}</td><td class="muted">${esc(x.type)}</td><td>${esc(x.location)}</td><td>${esc(x.participants.slice(0,5).join('、'))}${x.participants.length>5?' …':''}</td><td>${x.sources.length}章</td></tr>`).join('')||'<tr><td colspan="7" class="empty">没有匹配事件</td></tr>'}</tbody></table></div>${pager(state.eventPage,list.length)}</div>`;$('#eventCategory').addEventListener('change',e=>{state.eventCategory=e.target.value;state.eventPage=1;renderEvents()});bindSearch('#eventQuery','eventQuery',()=>{state.eventPage=1;renderEvents()});const root=$('#events');bindPaging(root,delta=>{state.eventPage+=delta;renderEvents()});root.querySelectorAll('[data-event-id]').forEach(b=>b.addEventListener('click',()=>showEvent(DATA.events.find(x=>x.id===b.dataset.eventId))))}
function renderRelations(){const cats=DATA.relationCategories||[];const list=DATA.relations.filter(x=>(state.relationCategory==='全部类别'||x.category===state.relationCategory)&&(!state.relationQuery||matchesQuery(`${x.from} ${x.to} ${x.rel} ${x.sourceTitle}`,state.relationQuery)));const page=slicePage(list,state.relationPage);const counts={};DATA.relations.forEach(x=>{counts[x.category]=(counts[x.category]||0)+1});$('#relations').innerHTML=`<div class="section-head"><div><h2>关系索引</h2><p>${metrics.relations} 条关系完整保留；自由文本关系已归入 ${cats.length} 个类别，原文仍可查。${DATA.relationScope==='induced'?'当前为分部范围：只列出两端都属于本范围的关系（诱导子图），跨范围关系请切到全书报告查看。':'当前为全书范围：保留全部关系（含跨部关系）。'}</p></div></div><div class="panel"><div class="toolbar"><label>类别</label><select id="relationCategory"><option value="全部类别" ${state.relationCategory==='全部类别'?'selected':''}>全部类别（${metrics.relations}）</option>${cats.map(c=>`<option ${state.relationCategory===c?'selected':''}>${esc(c)}</option>`).join('')}</select><span class="muted">当前类别 ${counts[state.relationCategory]||metrics.relations} 条</span><input class="search grow" id="relationQuery" value="${esc(state.relationQuery)}" placeholder="人物、关系或来源章节"></div><div class="table-wrap"><table class="data-table"><thead><tr><th>主体</th><th>类别</th><th>关系</th><th>对象</th><th>来源</th></tr></thead><tbody>${page.map(x=>`<tr><td>${esc(x.from)}${epTag(x.from,x.endpointKind&&x.endpointKind.from)}</td><td>${catBadge(x.category,relCatColor(x.category))}</td><td>${esc(x.rel)}</td><td>${esc(x.to)}${epTag(x.to,x.endpointKind&&x.endpointKind.to)}</td><td>${esc(x.sourceTitle)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">没有匹配关系</td></tr>'}</tbody></table></div>${pager(state.relationPage,list.length)}</div>`;$('#relationCategory').addEventListener('change',e=>{state.relationCategory=e.target.value;state.relationPage=1;renderRelations()});bindSearch('#relationQuery','relationQuery',()=>{state.relationPage=1;renderRelations()});const root=$('#relations');bindPaging(root,delta=>{state.relationPage+=delta;renderRelations()})}
const HAN_NUM=['','一','二','三','四','五','六','七','八','九'];
const hanNum=n=>{n=Math.round(n);if(n<=0)return String(n);if(n<=10)return HAN_NUM[n];if(n<20)return '十'+(n%10?HAN_NUM[n%10]:'');const t=Math.floor(n/10),u=n%10;return HAN_NUM[t]+'十'+(u?HAN_NUM[u]:'')};
const reignOf=year=>{const y=Number(year);if(!y)return null;return (DATA.reigns||[]).find(r=>y>=r.start&&y<=r.end)||null};
const eraTag=year=>{const y=parseInt(year,10);if(!y)return '';const r=reignOf(y);if(!r)return '';return `<span class="era-tag">${esc(r.era)}${hanNum(y-r.start+1)}年</span>`};
const reignColor=(i)=>`hsl(${(i*137)%360},38%,${i%2?46:38}%)`;
function renderDynasty(){const reigns=DATA.reigns||[];if(!reigns.length){$('#dynasty').innerHTML='<div class="empty">暂无帝王数据</div>';return}
const minY=1368,maxY=1644,span=maxY-minY+1;
const counts=reigns.map(r=>DATA.timeline.filter(e=>e.year_start>=r.start&&e.year_start<=r.end).length);
const perYear={};DATA.timeline.forEach(e=>{const y=e.year_start;if(y>=minY&&y<=maxY)perYear[y]=(perYear[y]||0)+1});
const maxPerYear=Math.max(...Object.values(perYear),1);
let bars='';for(let y=minY;y<=maxY;y++){const c=perYear[y]||0;const r=reignOf(y);bars+=`<span style="height:${c?Math.max(10,c*100/maxPerYear):3}%;background:${r?reignColor(r.order-1):'#c9bfae'}" title="${y}年${r?' · '+esc(r.era):''} · 事件 ${c} 件"></span>`}
const segs=reigns.map((r,i)=>`<div class="dynasty-seg" data-era="${esc(r.era)}" style="width:${(r.end-r.start+1)*100/span}%;background:${reignColor(i)}" title="${esc(r.era)}（${esc(r.name)} ${esc(r.temple)}）${r.start}-${r.end} · 在位 ${r.end-r.start+1} 年 · 本朝事件 ${counts[i]} 件"></div>`).join('');
// 年号标签在色带上、下两层交替错行（row0=上层 row1=下层），left 百分比与色段同一坐标系，天然对齐：条宽即在位年数，短命年号只有 1~2% 宽，单层排布必然糊成一团
const _lr=[-1e9,-1e9],_lrows=[[],[]];
reigns.forEach(r=>{
  const w=(r.end-r.start+1)*100/span;
  const center=((r.start-minY)+(r.end-r.start+1)/2)*100/span;
  const half=Math.max(w/2,(r.era.length*3.0+1.4)/2);
  let row=(center-half>_lr[0]+0.5)?0:((center-half>_lr[1]+0.5)?1:(_lr[0]<=_lr[1]?0:1));
  _lr[row]=center+half;
  _lrows[row].push(`<span class="dynasty-label row-${row}${state.dynastyEra===r.era?' active':''}" style="left:${center}%" data-era="${esc(r.era)}" title="${esc(r.era)} · ${esc(r.name)} · ${r.start}-${r.end}（${r.end-r.start+1} 年）">${esc(r.era)}</span>`);
});
const eraLabelsAbove=_lrows[0].join(''),eraLabelsBelow=_lrows[1].join('');
const sel=state.dynastyEra||'';
const cards=reigns.map((r,i)=>`<div class="dynasty-card ${sel===r.era?'active':''}" data-era="${esc(r.era)}" style="--cat:${reignColor(i)}"><h3>${esc(r.era)}</h3><div class="muted">${esc(r.name)} · ${esc(r.temple)} · ${r.start}-${r.end} · 在位${r.end-r.start+1}年</div><p>${esc(r.note)}</p><span class="tag" style="margin-top:8px">${counts[i]} 件大事</span></div>`).join('');
let detail='';
if(sel){const idx=reigns.findIndex(r=>r.era===sel);if(idx>=0){const r=reigns[idx];
const evs=DATA.timeline.filter(e=>e.year_start>=r.start&&e.year_start<=r.end).sort((a,b)=>a.year_start-b.year_start);
const persons={};evs.forEach(e=>(e.participants||[]).forEach(p=>persons[p]=(persons[p]||0)+1));
const topP=Object.entries(persons).sort((a,b)=>b[1]-a[1]).slice(0,12);
detail=`<div class="panel" style="margin-top:14px"><div class="section-head"><div><h2 style="font-size:18px">${esc(r.era)}一朝 · ${esc(r.name)}（${esc(r.temple)}）</h2><p>${r.start}-${r.end} · 在位 ${r.end-r.start+1} 年 · ${esc(r.note)}</p></div><span class="muted">再次点击同一卡片可收起</span></div><div class="dynasty-detail-grid"><div><h3 style="margin:0 0 8px;font-size:14px">本朝大事（${evs.length}）</h3>${evs.slice(0,14).map(e=>`<div class="dynasty-event-row"><span><span class="cat-dot" style="--cat:${eventCatColor(e.category)}"></span><button class="link-button" data-event-id="${e.id}">${esc(e.name)}</button></span><span class="muted">${esc(e.year||'')} · ${esc((e.participants||[]).slice(0,3).join('、'))}</span></div>`).join('')||'<div class="empty">本朝暂无可纪年大事</div>'}</div><div><h3 style="margin:0 0 8px;font-size:14px">本朝活跃人物</h3><div class="source-row">${topP.map(([p,c])=>`<span class="source-chip">${esc(p)} · ${c} 件</span>`).join('')||'<span class="muted">暂无</span>'}</div></div></div></div>`}}
$('#dynasty').innerHTML=`<div class="section-head"><div><h2>帝王谱系</h2><p>十六位天子、十七段年号；${DATA.timeline.length} 件可纪年大事按在位期自动归位，条带宽度即在位时长。</p></div><span class="status">帝系为人工整理 · 事件自动对位</span></div><div class="panel" style="margin-bottom:14px"><div class="section-head"><div><h2 style="font-size:16px">一、在位条带与逐年大事热度</h2><p>中条为年号区间（1368-1644），年号标签在色带上、下方交替错行并按区间居中；下条为逐年事件数，颜色随年号切换；悬停看具体年份。</p></div></div><div class="dynasty-labels above">${eraLabelsAbove}</div><div class="dynasty-band">${segs}</div><div class="dynasty-labels below">${eraLabelsBelow}</div><div class="dynasty-hist">${bars}</div><div class="dynasty-scale"><span>1368 · 洪武开国</span><span>1644 · 崇祯殉国</span></div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:16px">二、十六帝小传</h2><p>点击任一帝王卡片或上方年号条，展开本朝大事与活跃人物。</p></div></div><div class="dynasty-cards">${cards}</div></div>${detail}`;
document.querySelectorAll('#dynasty .dynasty-card,#dynasty .dynasty-seg,#dynasty .dynasty-label').forEach(el=>el.addEventListener('click',()=>{state.dynastyEra=state.dynastyEra===el.dataset.era?'':el.dataset.era;renderDynasty()}));
document.querySelectorAll('#dynasty [data-event-id]').forEach(b=>b.addEventListener('click',()=>showEvent(DATA.events.find(x=>x.id===b.dataset.eventId))))}
const EST_HINT=55;function renderChronicle(){const lives=(DATA.lifespans||[]).slice();if(!lives.length){$('#chronicle').innerHTML='<div class="empty">暂无年谱数据</div>';return}const GROUP_COLORS={'帝系':'#8d3025','开国功臣':'#b88b35','永乐群英':'#476b86','内阁文臣':'#527b5c','武将勋臣':'#8c6344','宦官佞幸':'#706b91','对手与民变':'#a24b55','文苑行者':'#6f6a63','东林党人':'#3f7d6e','忠烈':'#9c3b2e'};const minY=Math.min(...lives.map(x=>x.birth))-3,maxY=Math.max(...lives.map(x=>x.death))+3,span=maxY-minY;const pct=y=>(y-minY)*100/span;const reigns=DATA.reigns||[];let bands='';if(1368>minY)bands+=`<span class="chronicle-band" style="left:0;width:${pct(Math.min(1368,maxY))}%;background:#9d9a8d" title="明兴之前"></span>`;reigns.forEach(r=>{bands+=`<span class="chronicle-band" style="left:${pct(r.start)}%;width:${(r.end-r.start+1)*100/span}%;background:${reignColor(r.order-1)}" title="${esc(r.era)} ${r.start}-${r.end}"></span>`});if(maxY>1644)bands+=`<span class="chronicle-band" style="left:${pct(1645)}%;width:${pct(maxY)-pct(1645)}%;background:#9d9a8d" title="甲申之后"></span>`;let ticks='';for(let y=Math.ceil(minY/25)*25;y<=maxY;y+=25){ticks+=`<span class="chronicle-tick" style="left:${pct(y)}%">${y}</span>`}const groups=[];lives.slice().sort((a,b)=>a.birth-b.birth).forEach(l=>{let g=groups.find(x=>x.label===l.group);if(!g){g={label:l.group,items:[]};groups.push(g)}g.items.push(l)});const charSet=new Set(DATA.characters.map(c=>c.name));const rows=groups.map(g=>{const c=GROUP_COLORS[g.label]||'#9d9a8d';return `<div class="chronicle-group"><span class="cat-dot" style="--cat:${c}"></span>${esc(g.label)} · ${g.items.length} 人</div>`+g.items.map(l=>{const left=pct(l.birth),w=Math.max(.7,pct(l.death+1)-left);const estNote=l.life_estimated?`\n生年不详，按卒年推 ${EST_HINT} 年示意（虚线条）`:(l.approx?'\n生卒年为通行说法（有异说）':'');const btn=charSet.has(l.name)?`<button class="link-button" data-person="${esc(l.name)}">${esc(l.name)}</button>`:esc(l.name);return `<div class="chronicle-row"><div class="chronicle-name">${btn}</div><div class="chronicle-track"><span class="chronicle-bar${l.life_estimated?' est':''}" style="left:${left}%;width:${w}%;background:${c}" title="${esc(l.name)} · ${l.life_estimated?'?':l.birth}–${l.death}${l.note?' · '+esc(l.note):''}${estNote}"></span></div></div>`}).join('')}).join('');$('#chronicle').innerHTML=`<div class="section-head"><div><h2>年谱 · 人物生平对照</h2><p>${lives.length} 位主要人物的生卒年横向展开，底色条带为十六帝在位期，人物与年号直接对位；点击人名打开详情。</p></div><span class="status draft">生卒年据通行史料整理 · 需史料核验</span></div><div class="panel"><div class="chronicle-wrap">${bands}<div class="chronicle-content"><div class="chronicle-axis">${ticks}</div>${rows}</div></div></div>`;document.querySelectorAll('#chronicle [data-person]').forEach(b=>b.addEventListener('click',()=>{const x=DATA.characters.find(y=>y.name===b.dataset.person);if(!x)return;showPerson(x.name)}))}/* P2-10：时间轴支持起止年份筛选（#view=timeline&from=1368&to=1644），
   与地址栏双向同步。判据用 year_start，与「按数值年份排序」同一口径；
   未填即不限，避免把「年份待考」的事件误当 0 年处理。 */
const timelineRange=()=>{const f=parseInt(state.timelineFrom,10),t=parseInt(state.timelineTo,10);return{from:Number.isFinite(f)?f:null,to:Number.isFinite(t)?t:null};};
function renderTimeline(){const cats=DATA.eventCategories||[];const R=timelineRange();const filtered=DATA.timeline.filter(x=>(state.timelineCategory==='全部类别'||x.category===state.timelineCategory)&&(R.from==null||x.year_start>=R.from)&&(R.to==null||x.year_start<=R.to));const page=slicePage(filtered,state.timelinePage);const groups=[];for(const event of page){const year=event.year||'年份待考';let group=groups.find(x=>x.year===year);if(!group){group={year,items:[]};groups.push(group)}group.items.push(event)}$('#timeline').innerHTML=`<div class="section-head"><div><h2>时间轴</h2><p>按数值年份排序；年份待考事件单独保留，不再混入历史顺序。${(R.from!=null||R.to!=null)?`当前筛选 ${R.from!=null?R.from:'不限'}—${R.to!=null?R.to:'不限'} 年（命中 ${filtered.length} / ${DATA.timeline.length} 件）。`:`可用起止年份筛选区间，例如 1368—1644。`}</p></div></div><div class="panel"><div class="toolbar"><label>类别</label><select id="timelineCategory"><option value="全部类别" ${state.timelineCategory==='全部类别'?'selected':''}>全部类别（${DATA.timeline.length}）</option>${cats.map(c=>`<option ${state.timelineCategory===c?'selected':''}>${esc(c)}</option>`).join('')}</select><label for="timelineFrom">起年</label><input class="search year-input" id="timelineFrom" type="number" inputmode="numeric" min="1368" max="1644" placeholder="不限" value="${esc(state.timelineFrom)}"><span class="muted">—</span><label for="timelineTo">止年</label><input class="search year-input" id="timelineTo" type="number" inputmode="numeric" min="1368" max="1644" placeholder="不限" value="${esc(state.timelineTo)}"><button class="action" id="timelineClear" ${(R.from==null&&R.to==null)?'disabled':''}>清除区间</button><span class="muted">圆点颜色即事件类别</span></div><div class="timeline">${groups.map(g=>`<div class="year-group"><h3>${esc(g.year)}${eraTag(g.year)}</h3>${g.items.map(x=>`<div class="timeline-item"><span class="cat-dot" style="--cat:${eventCatColor(x.category)}" title="${esc(x.category)}"></span><button data-event-id="${x.id}">${esc(x.name)}</button><span class="muted"> · ${esc(x.participants.slice(0,4).join('、'))}</span></div>`).join('')}</div>`).join('')||'<div class="empty">当前区间没有可纪年事件</div>'}</div>${pager(state.timelinePage,filtered.length)}</div><div class="panel unknown"><div class="section-head"><div><h2 style="font-size:18px">年份待考</h2><p>${DATA.unknownTimeline.length} 件事件仍在事件索引中；它们没有数字年份，不受区间筛选影响。</p></div></div><div class="source-row">${DATA.unknownTimeline.slice(0,80).map(x=>`<button class="source-chip link-button" data-event-id="${x.id}">${esc(x.name)}</button>`).join('')}</div></div>`;$('#timelineCategory').addEventListener('change',e=>{state.timelineCategory=e.target.value;state.timelinePage=1;renderTimeline()});
 const applyRange=()=>{state.timelinePage=1;writeHash({view:'timeline',from:state.timelineFrom,to:state.timelineTo});renderTimeline()};
 $('#timelineFrom').addEventListener('change',e=>{state.timelineFrom=e.target.value.trim();applyRange()});
 $('#timelineTo').addEventListener('change',e=>{state.timelineTo=e.target.value.trim();applyRange()});
 $('#timelineClear').addEventListener('click',()=>{state.timelineFrom='';state.timelineTo='';applyRange()});
 const root=$('#timeline');bindPaging(root,delta=>{state.timelinePage+=delta;renderTimeline()});root.querySelectorAll('[data-event-id]').forEach(b=>b.addEventListener('click',()=>showEvent(DATA.events.find(x=>x.id===b.dataset.eventId))))}
renderOverview();state.rendered.overview=true;

/* ============================================================
   Phase 6：URL deep link + 搜索命中高亮 + 无障碍
   地址栏即状态：#view=characters&person=于谦&detail=1
   ============================================================ */

/* ---- 6.1 地址栏状态 ---- */
const HASH_VIEWS=new Set(['overview','distribution','visuals','locations','map','characters','events','relations','timeline','dynasty','chronicle','insight']);
let _hashApplying=false;
function readHash(){
  const raw=String(location.hash||'').replace(/^#/,'');
  const out={};
  if(!raw)return out;
  raw.split('&').forEach(part=>{
    if(!part)return;
    const eq=part.indexOf('=');
    const key=eq<0?part:part.slice(0,eq);
    const val=eq<0?'':decodeURIComponent(part.slice(eq+1));
    if(key)out[key]=val;
  });
  return out;
}
function writeHash(params){
  if(_hashApplying)return;
  const cur=readHash();
  Object.keys(params||{}).forEach(k=>{const v=params[k];if(v===null||v===undefined||v==='')delete cur[k];else cur[k]=v});
  const qs=Object.keys(cur).filter(k=>cur[k]!=='').map(k=>k+'='+encodeURIComponent(cur[k])).join('&');
  try{history.replaceState(null,'',location.pathname+location.search+(qs?'#'+qs:''))}catch(_){}
}
/* 实体参数互斥：打开事件时就该把上一次的 person/place 清掉，否则复制出去的地址会同时指向两张卡 */
function entityHash(kind,name){const o={person:null,event:null,place:null,detail:null};if(kind)o[kind]=name;return o;}
const RENDERERS={overview:renderOverview,distribution:renderDistribution,visuals:renderVisuals,locations:renderLocations,map:renderMap,characters:renderCharacters,events:renderEvents,relations:renderRelations,timeline:renderTimeline,dynasty:renderDynasty,chronicle:renderChronicle,insight:renderInsight};
function rerender(view){const key=view||state.view;const fn=RENDERERS[key];if(!fn)return;try{fn();state.rendered[key]=true;}catch(err){reportRuntimeError('渲染',(err&&err.message)||err);}}
const cssEscape=s=>window.CSS&&CSS.escape?CSS.escape(s):String(s).replace(/["\\]/g,'\\$&');
function locatePersonCard(name){
  const host=$('#characters');if(!host||!name)return;
  const card=host.querySelector(`[data-char="${cssEscape(name)}"]`);
  if(!card)return;
  card.classList.add('flash');
  try{card.scrollIntoView({block:'center',behavior:'smooth'})}catch(_){card.scrollIntoView()}
  setTimeout(()=>card.classList.remove('flash'),2600);
}
function applyDeepLink(){
  const p=readHash();
  if(!Object.keys(p).length)return;
  _hashApplying=true;
  try{
    if(p.view&&HASH_VIEWS.has(p.view))setView(p.view);
    if(p.map==='voyage'||p.map==='pilgrim'){state.mapMode=p.map;if(state.view==='map')rerender('map')}
    if(p.era){state.dynastyEra=p.era;if(state.view==='dynasty')rerender('dynasty')}
    // 双模式图：net=full 人物图 / net=entity 实体图
    if(p.net==='full'||p.net==='entity'||p.net==='ego'){state.netMode=p.net;if(state.view==='visuals')rerender('visuals')}
    // 时间轴区间：from / to（仅时间轴视图消费；年份待考事件不受影响）
    if(p.from!==undefined||p.to!==undefined){
      state.timelineFrom=String(p.from||'').trim();state.timelineTo=String(p.to||'').trim();
      if(state.view==='timeline'){state.timelinePage=1;rerender('timeline')}
    }
    if(p.q){
      const key={locations:'locQuery',characters:'charQuery',events:'eventQuery',relations:'relationQuery'}[state.view];
      if(key){
        state[key]=p.q;
        if(state.view==='locations')state.locPage=1;
        if(state.view==='characters')state.charPage=1;
        if(state.view==='events')state.eventPage=1;
        if(state.view==='relations')state.relationPage=1;
        rerender(state.view);
      }
    }
    if(p.person){
      if(state.view!=='characters')setView('characters');
      const x=DATA.characters.find(y=>y.name===p.person)||DATA.characters.find(y=>(y.aliases||[]).includes(p.person))||DATA.characters.find(y=>(DATA.aliasIndex||{})[p.person]===y.name);
      const nm=x?x.name:p.person;
      state.charQuery=nm;state.charPage=1;rerender('characters');
      locatePersonCard(nm);
      if(p.detail==='1'&&x)showPerson(x.name);
    }else if(p.event){
      const ev=DATA.events.find(e=>e.id===p.event)||DATA.events.find(e=>e.name===p.event);
      if(ev){if(state.view!=='events')setView('events');showEvent(ev)}
    }else if(p.place){
      const loc=DATA.locations.find(l=>l.ancient===p.place)||DATA.locations.find(l=>(l.mentionedAs||[]).includes(p.place));
      if(loc){if(state.view!=='map'&&state.view!=='locations')setView('locations');showLocation(loc)}
    }
  }finally{_hashApplying=false}
}

/* ===== 洞察联动：正文实体可点击 + 详情页反向入口 =====
   索引由构建期 core/insight_link.py 生成（DATA.insightIndex），这里只消费结果：
   正向=把该节命中的人物/地点/事件名包成按钮；反向=详情页列出「相关洞察」章节。
   只改文本节点，绝不碰标签与属性，避免破坏原文里的 <strong>/<h4> 结构。*/
// 注意：DATA 是脚本作用域的 const（不是 window 的属性），
// 这里必须用裸标识符 typeof 判空——写 window.DATA 会恒为 undefined（已踩过）。
function insightIdx(){return (typeof DATA!=='undefined'&&DATA.insightIndex)||null}
function insightChips(kind,key){
  const IX=insightIdx();if(!IX)return '';
  const map=kind==='person'?IX.byPerson:kind==='place'?IX.byPlace:IX.byEvent;
  const sids=(map&&map[key])||[];if(!sids.length)return '';
  return sids.map(sid=>'<button class="ins-chip" type="button" data-ins-goto="'+esc(sid)+'">'+esc((IX.titles&&IX.titles[sid])||sid)+'</button>').join('');
}
function insightBlock(kind,key){
  const chips=insightChips(kind,key);if(!chips)return '';
  return '<div class="detail-block detail-wide"><strong>相关洞察</strong><p class="ins-chips">'+chips+'</p></div>';
}
function gotoInsight(sid){
  // 从详情弹窗里点「相关洞察」时，弹窗是 top-layer，会把滚动后的正文完全挡住
  // ——必须先关掉弹窗，否则用户点了像没反应。
  const _dlg=$('#detailDialog');if(_dlg&&_dlg.open)_dlg.close();
  if(state.view!=='insight'){setView('insight');rerender('insight')}
  writeHash({view:'insight'});
  const el=document.getElementById('ins-'+sid);
  if(!el){failBar('ins-goto','未找到洞察章节：'+sid,{level:'warn'});return}
  el.scrollIntoView({behavior:'smooth',block:'start'});el.classList.add('ins-hl');setTimeout(function(){el.classList.remove('ins-hl')},1800)
}
function linkifyInsight(){
  const IX=insightIdx();if(!IX||!IX.sections)return;
  const arts=document.querySelectorAll('#insight article.insight-sec');
  for(let ai=0;ai<arts.length;ai++){
    const art=arts[ai],sid=(art.id||'').replace(/^ins-/,''),hits=IX.sections[sid];
    if(!hits)continue;
    const items=[];
    (hits.p||[]).forEach(function(s){items.push([s,'p',(IX.alias||{})[s]||s])});
    (hits.l||[]).forEach(function(s){items.push([s,'l',(IX.placeAlias||{})[s]||s])});
    (hits.e||[]).forEach(function(s){items.push([s,'e',s])});
    if(!items.length)continue;
    items.sort(function(a,b){return b[0].length-a[0].length});  // 长名优先，短名不截断长名
    const bySurface={};items.forEach(function(it){if(!(it[0] in bySurface))bySurface[it[0]]=it});
    const re=new RegExp(items.map(function(it){return it[0].replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}).join('|'),'g');
    const walker=document.createTreeWalker(art,NodeFilter.SHOW_TEXT,null);
    const nodes=[];let n;
    while((n=walker.nextNode())){
      if(!n.nodeValue||!n.nodeValue.trim())continue;
      const par=n.parentElement;
      if(!par||par.closest('a,button,script,style,code'))continue;
      nodes.push(n);
    }
    nodes.forEach(function(node){
      const text=node.nodeValue;re.lastIndex=0;
      if(!re.test(text)){re.lastIndex=0;return}
      re.lastIndex=0;
      const frag=document.createDocumentFragment();let last=0,m;
      while((m=re.exec(text))){
        if(m.index>last)frag.appendChild(document.createTextNode(text.slice(last,m.index)));
        const it=bySurface[m[0]];
        if(it){
          const b=document.createElement('button');
          b.className='ins-link ins-'+it[1];b.type='button';b.textContent=m[0];
          b.setAttribute('data-ins-'+it[1],it[2]);
          b.title=it[1]==='p'?'查看人物卡':it[1]==='l'?'查看地点':'查看事件';
          frag.appendChild(b);
        }else{frag.appendChild(document.createTextNode(m[0]))}
        last=m.index+m[0].length;
      }
      if(last<text.length)frag.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(frag,node);
    });
  }
}
document.addEventListener('click',function(e){
  const t=e.target;
  const lnk=t&&t.closest?t.closest('.ins-link'):null;
  if(lnk){
    // 找不到目标时必须给出可见反馈——静默 return 会让用户以为链接是死的。
    const _p=lnk.getAttribute('data-ins-p'),_l=lnk.getAttribute('data-ins-l'),_e=lnk.getAttribute('data-ins-e');
    if(_p){if(!showPerson(_p))failBar('ins-p','未找到人物：'+_p,{level:'warn'});return}
    if(_l){const loc=DATA.locations.find(function(l){return l.ancient===_l});if(loc)showLocation(loc);else failBar('ins-l','未找到地点：'+_l,{level:'warn'});return}
    if(_e){const ev=DATA.events.find(function(x){return x.name===_e});if(ev)showEvent(ev);else failBar('ins-e','未找到事件：'+_e,{level:'warn'});return}
    return;
  }
  const chip=t&&t.closest?t.closest('.ins-chip'):null;
  if(chip&&chip.getAttribute('data-ins-goto'))gotoInsight(chip.getAttribute('data-ins-goto'));
});

window.addEventListener('hashchange',applyDeepLink);
document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',()=>writeHash(Object.assign({view:b.dataset.view},entityHash(null,null),{from:null,to:null}))));
/* 打开详情时把实体写进地址栏——复制地址即可分享同一张卡 */
const _showEvent=showEvent;
showEvent=function(event){_showEvent(event);writeHash(Object.assign({view:state.view},entityHash('event',event&&event.id)))};
const _showLocation=showLocation;
showLocation=function(x){_showLocation(x);if(x)writeHash(Object.assign({view:state.view},entityHash('place',x.ancient)))};
$('#detailDialog').addEventListener('close',()=>writeHash({detail:null}));

/* ---- 6.2 搜索命中高亮 ---- */
let _hlTimer=null,_hlSuppress=0;
function clearMarks(host){host.querySelectorAll('mark.hl').forEach(m=>{const t=document.createTextNode(m.textContent);if(m.parentNode)m.parentNode.replaceChild(t,m)})}
/* 只标 2 字以上的命中：单字（如「王」）会把半个页面涂黄，反而看不清 */
function markTerms(host,terms){
  const list=[...new Set(terms.filter(t=>t&&String(t).length>=2))];
  if(!list.length)return;
  const walker=document.createTreeWalker(host,NodeFilter.SHOW_TEXT,null);
  const targets=[];let node;
  while((node=walker.nextNode())){
    const p=node.parentNode;if(!p)continue;
    const tag=p.nodeName;
    if(tag==='SCRIPT'||tag==='STYLE'||tag==='MARK'||tag==='INPUT'||tag==='TEXTAREA'||tag==='OPTION'||tag==='SELECT')continue;
    const low=String(node.nodeValue||'').toLowerCase();
    if(!low.trim())continue;
    if(list.some(t=>low.includes(String(t).toLowerCase())))targets.push(node);
  }
  targets.forEach(node=>{
    const frag=document.createDocumentFragment();let rest=node.nodeValue;
    while(rest){
      let bestIdx=-1,bestTerm='';
      list.forEach(t=>{const idx=rest.toLowerCase().indexOf(String(t).toLowerCase());if(idx>=0&&(bestIdx<0||idx<bestIdx)){bestIdx=idx;bestTerm=rest.substr(idx,String(t).length)}});
      if(bestIdx<0){frag.appendChild(document.createTextNode(rest));break}
      if(bestIdx>0)frag.appendChild(document.createTextNode(rest.slice(0,bestIdx)));
      const mk=document.createElement('mark');mk.className='hl';mk.textContent=bestTerm;frag.appendChild(mk);
      rest=rest.slice(bestIdx+bestTerm.length);
    }
    if(node.parentNode)node.parentNode.replaceChild(frag,node);
  });
}
function refreshHighlight(){
  const key={locations:state.locQuery,characters:state.charQuery,events:state.eventQuery,relations:state.relationQuery}[state.view];
  const host=document.getElementById(state.view);
  if(!host)return;
  _hlSuppress=Date.now()+320;      // 自己造成的改动不再触发观察器
  clearMarks(host);
  if(host.normalize)host.normalize();
  const q=String(key||'').trim();
  if(!q)return;
  markTerms(host,[q,(DATA.aliasIndex||{})[q]]);
}
function scheduleHighlight(){
  if(Date.now()<_hlSuppress)return;
  clearTimeout(_hlTimer);
  _hlTimer=setTimeout(refreshHighlight,110);
}
if(window.MutationObserver){
  const mainEl=document.querySelector('main');
  if(mainEl)new MutationObserver(scheduleHighlight).observe(mainEl,{childList:true,subtree:true});
}

/* ---- 6.3 无障碍：tabs 语义 + 方向键切换 ---- */
const _tabsNav=document.querySelector('.tabs');
function syncTabA11y(){
  if(!_tabsNav)return;
  _tabsNav.querySelectorAll('button').forEach(b=>{
    const on=b.dataset.view===state.view;
    b.setAttribute('aria-selected',on?'true':'false');
    b.tabIndex=on?0:-1;
  });
}
if(_tabsNav){
  _tabsNav.setAttribute('role','tablist');
  _tabsNav.setAttribute('aria-label','报告视图');
  _tabsNav.querySelectorAll('button').forEach(b=>{b.setAttribute('role','tab');b.setAttribute('aria-controls',b.dataset.view)});
  document.querySelectorAll('main .view').forEach(v=>v.setAttribute('role','tabpanel'));
  _tabsNav.addEventListener('keydown',e=>{
    if(['ArrowRight','ArrowLeft','Home','End'].indexOf(e.key)<0)return;
    const btns=[..._tabsNav.querySelectorAll('button')];
    const cur=btns.findIndex(b=>b.dataset.view===state.view);
    let n=cur;
    if(e.key==='ArrowRight')n=(cur+1)%btns.length;
    else if(e.key==='ArrowLeft')n=(cur-1+btns.length)%btns.length;
    else if(e.key==='Home')n=0;
    else n=btns.length-1;
    e.preventDefault();btns[n].focus();btns[n].click();
  });
  const _baseSetView=setView;
  setView=function(view){_baseSetView(view);syncTabA11y()};
  syncTabA11y();
}

/* ---- P3-03 启动自检与全局异常兜底 ---- */
window.__MING_READY=true;   // 数据已解析、主脚本已执行（骨架里的守卫脚本据此判断是否需要报错）
window.addEventListener('error',e=>{if(e&&e.message)reportRuntimeError('脚本',e.message)});
window.addEventListener('unhandledrejection',e=>{const r=e&&e.reason;reportRuntimeError('异步',(r&&(r.message||r))||'未捕获的 Promise 拒绝')});
/* 数据完整性：必需字段缺失（构建异常或文件被裁剪）时给出可见提示，而不是留下一片空白视图 */
const _missingKeys=['characters','events','locations','relations','chapters'].filter(k=>!DATA[k]);
if(_missingKeys.length)failBar('data','内嵌数据不完整，缺少字段：'+_missingKeys.join('、')+'，部分视图可能空白，请重新生成报告。',{level:'error',retry:()=>location.reload(),retryLabel:'重新加载'});

/* 首屏按地址栏还原（无 hash 时原样停在总览） */
try{applyDeepLink();}catch(err){reportRuntimeError('深链',(err&&err.message)||err);}

