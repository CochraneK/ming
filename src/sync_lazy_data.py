# -*- coding: utf-8 -*-
"""把 V6 search-index 钩子安全写入 V3 experience.js。

experience.js 仍是全局搜索/首页叙事/图谱阅读器的人工维护源。本脚本只改命令面板：
1) 搜索结果缓存区分 boot / search / full；
2) 打开命令面板只加载轻量 search-index.js；
3) 真正选择人物/地点/事件后才加载 data-full.js 并回查最终实体。

采用 V5→V6 精确迁移 + V6 幂等标记；standalone 没有 loader，仍直接使用完整 DATA。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TARGET = BASE / "web" / "js" / "experience.js"
OLD_MARKER = "/* V5_LAZY_COMMAND_DATA */"
MARKER = "/* V6_SEARCH_INDEX_COMMAND_DATA */"


def _sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise SystemExit("V6 search-index 锚点异常（%s）：匹配 %d 处" % (label, count))
    return updated


def render_source(source: str) -> str:
    if MARKER in source:
        return source
    if OLD_MARKER not in source:
        raise SystemExit("V6 search-index 找不到 V5 命令面板标记")

    text = source.replace(OLD_MARKER, MARKER, 1)
    text = text.replace(
        "let commandRows=null,commandRowsFull=false,commandResults=[],commandActive=0,commandLastFocus=null;",
        "let commandRows=null,commandRowsMode='',commandResults=[],commandActive=0,commandLastFocus=null;",
        1,
    )

    build_block = r'''function commandHasFullData(){return typeof window.__MING_ENSURE_FULL_DATA!=='function'||window.__MING_FULL_DATA_READY===true;}
function commandHasSearchIndex(){return window.__MING_SEARCH_INDEX_READY===true&&window.__MING_SEARCH_INDEX__&&Array.isArray(window.__MING_SEARCH_INDEX__.rows);}
function commandMode(){return commandHasFullData()?'full':(commandHasSearchIndex()?'search':'boot');}
function buildCommandRows(){
  const mode=commandMode();
  if(commandRows&&commandRowsMode===mode)return commandRows;
  const rows=[];
  VIEWS.forEach(([id,title,keys])=>rows.push({kind:'view',id,title,meta:'切换到 '+title,search:norm(title+' '+keys)}));
  if(mode==='full'){
    (DATA.characters||[]).forEach(x=>{
      const aliases=(x.aliases||[]).join(' '),p=x.profile||{};
      rows.push({kind:'person',id:x.name,title:x.name,meta:[x.role,(p.factions||[]).join('、'),x.life].filter(Boolean).join(' · '),search:norm([x.name,aliases,x.role,x.faction,p.raw,(p.factions||[]).join(' ')].join(' ')),raw:x});
    });
    (DATA.locations||[]).forEach(x=>rows.push({kind:'place',id:x.ancient,title:x.ancient,meta:[x.modern,x.region].filter(Boolean).join(' · '),search:norm([x.ancient,x.modern,x.region,(x.altNames||[]).join(' '),(x.mentionedAs||[]).join(' ')].join(' ')),raw:x}));
    (DATA.events||[]).forEach(x=>rows.push({kind:'event',id:x.id,title:x.name,meta:[x.year||'年份待考',x.category,x.location].filter(Boolean).join(' · '),search:norm([x.name,x.year,x.category,x.type,x.location,(x.participants||[]).join(' ')].join(' ')),raw:x}));
  }else if(mode==='search'){
    (window.__MING_SEARCH_INDEX__.rows||[]).forEach(x=>rows.push({kind:x.kind,id:x.id,title:x.title,meta:x.meta||'',search:norm(x.search||x.title)}));
  }
  commandRows=rows;commandRowsMode=mode;
  return rows;
}
function commandScore'''
    text = _sub_once(
        text,
        r"function commandHasFullData\(\).*?\n}\nfunction commandScore",
        build_block,
        "build command rows",
    )

    open_block = r'''function openCommand(seed){
  const shell=commandShell();commandLastFocus=document.activeElement;shell.hidden=false;document.body.classList.add('command-open');document.querySelectorAll('.command-trigger').forEach(b=>b.setAttribute('aria-expanded','true'));
  const input=shell.querySelector('#commandInput');input.value=seed||'';commandActive=0;renderCommand(input.value);
  if(!commandHasFullData()&&!commandHasSearchIndex()&&typeof window.__MING_ENSURE_SEARCH_INDEX==='function'){
    window.__MING_ENSURE_SEARCH_INDEX('command').then(()=>{commandRows=null;commandRowsMode='';renderCommand(input.value);}).catch(err=>{
      const host=document.getElementById('commandResults');if(host)host.innerHTML='<div class="command-empty">搜索索引加载失败，可稍后重试。</div>';
      if(typeof failBar==='function')failBar('search-index','搜索索引加载失败：'+String((err&&err.message)||err),{level:'warn'});
    });
  }
  requestAnimationFrame(()=>input.focus());
}
function closeCommand'''
    text = _sub_once(
        text,
        r"function openCommand\(seed\)\{.*?\n}\nfunction closeCommand",
        open_block,
        "open command",
    )

    run_block = r'''function executeEntityCommand(r){
  if(r.kind==='person'){
    setView('characters');state.charQuery=r.title;state.charPage=1;if(typeof rerender==='function')rerender('characters');if(typeof locatePersonCard==='function')locatePersonCard(r.title);if(typeof showPerson==='function')showPerson(r.title);return;
  }
  if(r.kind==='place'){
    const x=(DATA.locations||[]).find(v=>v.ancient===r.id)||(DATA.locations||[]).find(v=>v.ancient===r.title);setView('locations');if(x&&typeof showLocation==='function')showLocation(x);return;
  }
  if(r.kind==='event'){
    const x=(DATA.events||[]).find(v=>v.id===r.id)||(DATA.events||[]).find(v=>v.name===r.title);setView('events');if(x&&typeof showEvent==='function')showEvent(x);
  }
}
function runCommand(r){
  closeCommand();
  if(r.kind==='view'){
    setView(r.id);if(typeof writeHash==='function')writeHash({view:r.id,person:null,event:null,place:null,detail:null});return;
  }
  const execute=()=>{commandRows=null;commandRowsMode='';executeEntityCommand(r);};
  if(commandHasFullData()){execute();return;}
  if(typeof window.__MING_ENSURE_FULL_DATA==='function'){
    window.__MING_ENSURE_FULL_DATA('command-result:'+r.kind).then(execute).catch(err=>{
      if(typeof failBar==='function')failBar('full-data','完整知识库加载失败：'+String((err&&err.message)||err),{level:'error',retry:()=>location.reload(),retryLabel:'重新加载'});
    });
    return;
  }
  execute();
}
function ensureCommandTrigger'''
    text = _sub_once(
        text,
        r"function runCommand\(r\)\{.*?\n}\nfunction ensureCommandTrigger",
        run_block,
        "run command",
    )
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 V6 search-index 钩子到 experience.js")
    parser.add_argument("--check", action="store_true", help="只检查，不写入")
    args = parser.parse_args(argv)
    source = TARGET.read_text(encoding="utf-8")
    updated = render_source(source)
    if updated == source:
        print("V6 search-index 钩子已同步")
        return 0
    if args.check:
        print("V6 search-index 钩子未同步；请运行 python src/sync_lazy_data.py")
        return 1
    TARGET.write_text(updated, encoding="utf-8")
    print("V6 search-index 钩子已写入 experience.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
