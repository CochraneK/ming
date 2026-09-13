/* ===== V3 产品体验层：全局搜索 / 首页叙事 / 图谱阅读器 =====
   这是 app.js 之后加载的渐进增强层：只调用现有 DATA / setView / show* / graph helpers，
   不复制业务渲染器。删除本文件后，12 个原视图仍应保持完整可用。 */
(function(){
'use strict';
if(typeof DATA==='undefined'||typeof setView!=='function')return;

const VIEWS=[
  ['overview','总览','知识库 首页 全局'],['distribution','分布','章节 密度 抽取 诊断'],
  ['timeline','时间轴','年份 事件 时间'],['dynasty','帝王','皇帝 年号 在位'],['chronicle','年谱','人物 生平 年代'],
  ['characters','人物','角色 人物卡'],['locations','地点','地名 地图 空间'],['events','事件','事件 索引'],['relations','关系','人物关系 网络'],
  ['visuals','图谱','网络 热力图 可视化'],['map','地图','圣地巡礼 郑和 航线'],['insight','洞察','跨学科 报告']
];
const TYPE_LABEL={view:'视图',person:'人物',place:'地点',event:'事件'};
const safe=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v==null?'':v).trim().toLowerCase();
const pct=(a,b)=>b?Math.round(a*100/b):0;

/* ------------------------------ 全局快捷搜索 ------------------------------ */
/* V5_LAZY_COMMAND_DATA */
let commandRows=null,commandRowsFull=false,commandResults=[],commandActive=0,commandLastFocus=null;
function commandHasFullData(){return typeof window.__MING_ENSURE_FULL_DATA!=='function'||window.__MING_FULL_DATA_READY===true;}
function buildCommandRows(){
  const full=commandHasFullData();
  if(commandRows&&commandRowsFull===full)return commandRows;
  const rows=[];
  VIEWS.forEach(([id,title,keys])=>rows.push({kind:'view',id,title,meta:'切换到 '+title,search:norm(title+' '+keys)}));
  (DATA.characters||[]).forEach(x=>{
    const aliases=(x.aliases||[]).join(' '),p=x.profile||{};
    rows.push({kind:'person',id:x.name,title:x.name,meta:[x.role,(p.factions||[]).join('、'),x.life].filter(Boolean).join(' · '),search:norm([x.name,aliases,x.role,x.faction,p.raw,(p.factions||[]).join(' ')].join(' ')),raw:x});
  });
  (DATA.locations||[]).forEach(x=>rows.push({kind:'place',id:x.ancient,title:x.ancient,meta:[x.modern,x.region].filter(Boolean).join(' · '),search:norm([x.ancient,x.modern,x.region,(x.altNames||[]).join(' '),(x.mentionedAs||[]).join(' ')].join(' ')),raw:x}));
  (DATA.events||[]).forEach(x=>rows.push({kind:'event',id:x.id,title:x.name,meta:[x.year||'年份待考',x.category,x.location].filter(Boolean).join(' · '),search:norm([x.name,x.year,x.category,x.type,x.location,(x.participants||[]).join(' ')].join(' ')),raw:x}));
  commandRows=rows;commandRowsFull=full;
  return rows;
}
function commandScore(row,q){
  const t=norm(row.title);if(!q)return row.kind==='view'?90:(row.kind==='person'?30:10);
  if(t===q)return 140;
  if(t.startsWith(q))return 120-Math.min(t.length-q.length,20);
  const i=row.search.indexOf(q);return i<0?-1:90-Math.min(i,45);
}
function commandShell(){
  let shell=document.getElementById('commandPalette');
  if(shell)return shell;
  shell=document.createElement('div');shell.id='commandPalette';shell.className='command-shell';shell.hidden=true;
  shell.innerHTML='<div class="command-panel" role="dialog" aria-modal="true" aria-labelledby="commandTitle">'+
    '<div class="command-head"><div><strong id="commandTitle">全局搜索</strong><span>人物 · 地点 · 事件 · 12 个视图</span></div><button class="command-close" type="button" aria-label="关闭全局搜索">×</button></div>'+
    '<label class="command-input-wrap"><span class="command-search-icon" aria-hidden="true">⌕</span><input id="commandInput" autocomplete="off" spellcheck="false" aria-controls="commandResults" aria-autocomplete="list" placeholder="搜索于谦、宁远、土木堡，或输入“时间轴”…"><kbd>Esc</kbd></label>'+
    '<div id="commandResults" class="command-results" role="listbox"></div>'+
    '<div class="command-foot"><span>↑↓ 选择 · Enter 打开</span><span>快捷键 <kbd>⌘/Ctrl K</kbd> 或 <kbd>/</kbd></span></div></div>';
  document.body.appendChild(shell);
  shell.addEventListener('click',e=>{if(e.target===shell||e.target.closest('.command-close'))closeCommand();const b=e.target.closest('[data-command-index]');if(b){const i=Number(b.dataset.commandIndex);if(commandResults[i])runCommand(commandResults[i]);}});
  const input=shell.querySelector('#commandInput');
  input.addEventListener('input',()=>renderCommand(input.value));
  input.addEventListener('keydown',e=>{
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();moveCommand(e.key==='ArrowDown'?1:-1);return;}
    if(e.key==='Enter'){e.preventDefault();const r=commandResults[commandActive];if(r)runCommand(r);}
  });
  return shell;
}
function renderCommand(raw){
  const q=norm(raw),rows=buildCommandRows();
  commandResults=rows.map(r=>[commandScore(r,q),r]).filter(x=>x[0]>=0).sort((a,b)=>b[0]-a[0]||a[1].title.localeCompare(b[1].title,'zh-CN')).slice(0,12).map(x=>x[1]);
  commandActive=Math.min(commandActive,Math.max(0,commandResults.length-1));
  const host=document.getElementById('commandResults');if(!host)return;
  host.innerHTML=commandResults.length?commandResults.map((r,i)=>'<button type="button" role="option" id="commandOption'+i+'" aria-selected="'+(i===commandActive?'true':'false')+'" class="command-item'+(i===commandActive?' active':'')+'" data-command-index="'+i+'"><span class="command-kind">'+TYPE_LABEL[r.kind]+'</span><span class="command-copy"><strong>'+safe(r.title)+'</strong><small>'+safe(r.meta||'')+'</small></span><span class="command-enter" aria-hidden="true">↵</span></button>').join(''):'<div class="command-empty">没有匹配结果。可尝试人物别名、古地名、事件名或视图名称。</div>';
  const input=document.getElementById('commandInput');if(input)input.setAttribute('aria-activedescendant',commandResults.length?'commandOption'+commandActive:'');
}
function moveCommand(delta){
  if(!commandResults.length)return;commandActive=(commandActive+delta+commandResults.length)%commandResults.length;renderCommand(document.getElementById('commandInput').value);const el=document.getElementById('commandOption'+commandActive);if(el)el.scrollIntoView({block:'nearest'});
}
function openCommand(seed){
  const shell=commandShell();commandLastFocus=document.activeElement;shell.hidden=false;document.body.classList.add('command-open');document.querySelectorAll('.command-trigger').forEach(b=>b.setAttribute('aria-expanded','true'));
  const input=shell.querySelector('#commandInput');input.value=seed||'';commandActive=0;renderCommand(input.value);
  if(!commandHasFullData()&&typeof window.__MING_ENSURE_FULL_DATA==='function'){
    window.__MING_ENSURE_FULL_DATA('command').then(()=>{commandRows=null;renderCommand(input.value);}).catch(err=>{
      const host=document.getElementById('commandResults');if(host)host.innerHTML='<div class="command-empty">完整知识库加载失败，可稍后重试。</div>';
      if(typeof failBar==='function')failBar('full-data','完整知识库加载失败：'+String((err&&err.message)||err),{level:'error',retry:()=>location.reload(),retryLabel:'重新加载'});
    });
  }
  requestAnimationFrame(()=>input.focus());
}
function closeCommand(){
  const shell=document.getElementById('commandPalette');if(!shell||shell.hidden)return;shell.hidden=true;document.body.classList.remove('command-open');document.querySelectorAll('.command-trigger').forEach(b=>b.setAttribute('aria-expanded','false'));if(commandLastFocus&&document.contains(commandLastFocus))try{commandLastFocus.focus()}catch(_){}
}
function runCommand(r){
  closeCommand();
  if(r.kind==='view'){
    setView(r.id);if(typeof writeHash==='function')writeHash({view:r.id,person:null,event:null,place:null,detail:null});return;
  }
  if(r.kind==='person'){
    setView('characters');state.charQuery=r.title;state.charPage=1;if(typeof rerender==='function')rerender('characters');if(typeof locatePersonCard==='function')locatePersonCard(r.title);if(typeof showPerson==='function')showPerson(r.title);return;
  }
  if(r.kind==='place'){
    setView('locations');if(typeof showLocation==='function')showLocation(r.raw);return;
  }
  if(r.kind==='event'){
    setView('events');if(typeof showEvent==='function')showEvent(r.raw);
  }
}
function ensureCommandTrigger(){
  const stat=document.getElementById('headerStat');if(!stat||stat.querySelector('.command-trigger'))return;
  const b=document.createElement('button');b.type='button';b.className='command-trigger';b.setAttribute('aria-haspopup','dialog');b.setAttribute('aria-controls','commandPalette');b.setAttribute('aria-expanded','false');b.innerHTML='<span>全局搜索</span><kbd>⌘/Ctrl K</kbd>';b.addEventListener('click',()=>openCommand(''));stat.appendChild(b);
}
document.addEventListener('keydown',e=>{
  const tag=(e.target&&e.target.tagName)||'',editing=/^(INPUT|TEXTAREA|SELECT)$/.test(tag)||(e.target&&e.target.isContentEditable);
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openCommand('');return;}
  if(e.key==='/'&&!editing&&document.getElementById('commandPalette')?.hidden!==false){e.preventDefault();openCommand('');return;}
  if(e.key==='Escape'&&document.getElementById('commandPalette')?.hidden===false){e.preventDefault();closeCommand();}
});
const headerStat=document.getElementById('headerStat');if(headerStat&&window.MutationObserver)new MutationObserver(ensureCommandTrigger).observe(headerStat,{childList:true});ensureCommandTrigger();commandShell();

/* ------------------------------ 首页数据叙事 ------------------------------ */
function maxEntry(obj){return Object.entries(obj||{}).sort((a,b)=>b[1]-a[1])[0]||['暂无',0];}
function storyHTML(){
  const lp=pct(DATA.metrics.locatedLocations,DATA.metrics.locations),tp=pct(DATA.metrics.timedEvents,DATA.metrics.events);
  const graph=DATA.relationGraphFull||{nodes:[]};const hub=[...(graph.nodes||[])].sort((a,b)=>(b.degree||0)-(a.degree||0))[0];
  const chapters=(DATA.distribution&&DATA.distribution.chapters)||[];const dense=[...chapters].sort((a,b)=>(b.density||0)-(a.density||0))[0];
  const ev=maxEntry(DATA.cleaning&&DATA.cleaning.event_categories),rel=maxEntry(DATA.cleaning&&DATA.cleaning.relation_categories);
  return '<section class="v3-story panel" aria-labelledby="v3StoryTitle"><div class="v3-story-head"><div><span class="v3-eyebrow">DATA STORY</span><h3 id="v3StoryTitle">先读懂这份知识图谱，再进入细节</h3><p>下面是数据覆盖与结构信号，不是人物重要性或历史价值排名。</p></div><button class="command-inline" type="button" data-v3-command>搜索整库 <kbd>⌘K</kbd></button></div>'+
    '<div class="v3-story-grid"><article class="v3-story-card"><strong>覆盖度</strong><div class="v3-progress-row"><span>地点已定位</span><b>'+lp+'%</b></div><div class="v3-progress"><i style="width:'+lp+'%"></i></div><div class="v3-progress-row"><span>事件可纪年</span><b>'+tp+'%</b></div><div class="v3-progress"><i style="width:'+tp+'%"></i></div><p>'+DATA.metrics.locatedLocations+'/'+DATA.metrics.locations+' 个地点有坐标；'+DATA.metrics.timedEvents+'/'+DATA.metrics.events+' 件事件进入数值时间轴。</p></article>'+
    '<article class="v3-story-card"><strong>结构信号</strong><dl class="v3-signal-list"><div><dt>关系网络入口</dt><dd>'+(hub?safe(hub.name)+' · '+(hub.degree||0)+' 条关系':'暂无')+'</dd></div><div><dt>抽取密度峰值</dt><dd>'+(dense?safe(dense.title)+' · '+dense.density+'/万字':'暂无')+'</dd></div><div><dt>最多事件类别</dt><dd>'+safe(ev[0])+' · '+ev[1]+' 件</dd></div><div><dt>最多关系类别</dt><dd>'+safe(rel[0])+' · '+rel[1]+' 条</dd></div></dl></article></div>'+
    '<div class="v3-story-actions"><span>建议阅读：</span><button data-open-view="timeline">时间证据</button><button data-open-view="map">空间证据</button><button data-open-view="visuals">关系结构</button><button data-open-view="insight">跨学科解释</button></div></section>';
}
function ensureStory(){
  const host=document.getElementById('overview');if(!host||host.querySelector('.v3-story')||!host.querySelector('.summary-hero'))return;
  const box=document.createElement('div');box.innerHTML=storyHTML();const story=box.firstElementChild;const anchor=host.querySelector('.v2-journeys')||host.querySelector('.summary-hero');anchor.insertAdjacentElement('afterend',story);
  story.querySelector('[data-v3-command]').addEventListener('click',()=>openCommand(''));
}
const overview=document.getElementById('overview');if(overview&&window.MutationObserver)new MutationObserver(()=>requestAnimationFrame(ensureStory)).observe(overview,{childList:true});ensureStory();

/* ------------------------------ 图谱阅读器 / 聚焦降噪 ------------------------------ */
function readerMode(){
  const select=document.getElementById('netMode'),mode=(select&&select.value)||state.netMode;
  return mode==='full'||mode==='entity'?mode:'ego';
}
function graphForReader(mode){const m=mode||readerMode();return m==='entity'&&DATA.relationGraphEntities?DATA.relationGraphEntities:DATA.relationGraphFull;}
function graphReaderHTML(mode){
  const m=mode||readerMode(),g=graphForReader(m)||{nodes:[],links:[]},entity=m==='entity';const hubs=[...(g.nodes||[])].sort((a,b)=>(b.degree||0)-(a.degree||0)||String(a.name).localeCompare(String(b.name),'zh-CN')).slice(0,8);
  return '<div class="v3-graph-reader" data-mode="'+safe(m)+'"><div class="v3-graph-reader-head"><div><span class="v3-eyebrow">GRAPH READER</span><strong>'+(entity?'实体总图':'人物总图')+'怎么读</strong><p>节点越大，关系度数越高；线条颜色表示关系类别。点击节点后，无关节点自动降到 12% 不透明度，用邻域聚焦降低视觉噪声。</p></div><button type="button" class="action" data-v3-reset>复位全图</button></div>'+
    '<div class="v3-graph-tools"><label>定位节点 <input type="search" data-v3-node-search placeholder="输入人物或实体名，Enter 聚焦"></label><span class="v3-graph-status" role="status" aria-live="polite">'+(g.nodes||[]).length+' 节点 · '+(g.links||[]).length+' 关系</span></div>'+
    '<div class="v3-hubs"><span>高连接入口</span>'+hubs.map(n=>'<button type="button" data-v3-focus="'+safe(n.name)+'"><b>'+safe(n.name)+'</b><small>'+(n.degree||0)+' 条</small></button>').join('')+'</div>'+
    '<div class="v3-graph-explain"><span><i class="v3-dot node"></i>节点大小 = 关系度数</span><span><i class="v3-line"></i>线颜色 = 关系类别</span><span><i class="v3-dot focus"></i>点击 = 只突出一跳邻域</span>'+(entity?'<span>实体图包含人物、地点、机构、政权；节点总数不能读作人物数。</span>':'<span>人物图仅保留人物↔人物关系，适合观察人物关系结构。</span>')+'</div></div>';
}
function focusGraphName(raw,root){
  const q=norm(raw),g=graphForReader();if(!q||!g)return false;const nodes=g.nodes||[];const n=nodes.find(x=>norm(x.name)===q)||nodes.find(x=>norm(x.name).startsWith(q))||nodes.find(x=>norm(x.name).includes(q));
  const status=root&&root.querySelector('.v3-graph-status');if(!n){if(status)status.textContent='没有找到“'+raw+'”';return false;}if(typeof showFullNode==='function')showFullNode(n.name);if(status)status.textContent='已聚焦 '+n.name+' · '+(n.degree||0)+' 条关系';return true;
}
function bindGraphReader(root){
  if(root.dataset.bound==='1')return;root.dataset.bound='1';
  root.addEventListener('click',e=>{const f=e.target.closest('[data-v3-focus]');if(f){focusGraphName(f.dataset.v3Focus,root);return;}if(e.target.closest('[data-v3-reset]')){if(typeof resetFullHighlight==='function')resetFullHighlight();const s=root.querySelector('.v3-graph-status'),g=graphForReader();if(s&&g)s.textContent=(g.nodes||[]).length+' 节点 · '+(g.links||[]).length+' 关系';}});
  const input=root.querySelector('[data-v3-node-search]');if(input)input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();focusGraphName(input.value,root);}});
}
function ensureGraphReader(){
  const host=document.getElementById('visuals');if(!host)return false;let reader=host.querySelector('.v3-graph-reader');const mode=readerMode();
  if(mode==='ego'){if(reader)reader.remove();return false;}
  const full=host.querySelector('#fullNet');if(!full)return false;
  if(reader&&reader.dataset.mode!==mode){reader.remove();reader=null;}
  if(!reader){const box=document.createElement('div');box.innerHTML=graphReaderHTML(mode);reader=box.firstElementChild;full.parentNode.insertBefore(reader,full);}
  bindGraphReader(reader);return true;
}
let graphRetryTimer=null;
function scheduleGraphReader(){
  requestAnimationFrame(ensureGraphReader);
  clearTimeout(graphRetryTimer);graphRetryTimer=setTimeout(ensureGraphReader,180);
}
const visuals=document.getElementById('visuals');if(visuals&&window.MutationObserver)new MutationObserver(scheduleGraphReader).observe(visuals,{childList:true,subtree:true});
document.addEventListener('change',e=>{if(e.target&&e.target.id==='netMode')setTimeout(scheduleGraphReader,0)});
window.addEventListener('hashchange',()=>setTimeout(scheduleGraphReader,40));
scheduleGraphReader();setTimeout(ensureGraphReader,500);

window.__MING_EXPERIENCE_READY=true;
})();
