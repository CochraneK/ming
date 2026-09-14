# -*- coding: utf-8 -*-
"""把 V9 人物详情分片钩子安全写入 V3 experience.js。

V6 拆出 search-index，V7 改为实体领域加载，V9 再让人物实体把姓名传给 loader，
从而只加载该人物对应的 character-detail shard。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TARGET = BASE / "web" / "js" / "experience.js"
OLD_MARKERS = (
    "/* V6_SEARCH_INDEX_COMMAND_DATA */",
    "/* V7_VIEW_CHUNK_COMMAND_DATA */",
)
MARKER = "/* V9_SHARDED_CHARACTER_DETAIL_COMMAND_DATA */"


def _sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise SystemExit("V9 分片命令钩子锚点异常（%s）：匹配 %d 处" % (label, count))
    return updated


def render_source(source: str) -> str:
    if MARKER in source:
        return source
    old = next((marker for marker in OLD_MARKERS if marker in source), None)
    if not old:
        raise SystemExit("V9 分片命令钩子找不到旧命令面板标记")

    text = source.replace(old, MARKER, 1)
    run_block = r'''function runCommand(r){
  closeCommand();
  if(r.kind==='view'){
    setView(r.id);if(typeof writeHash==='function')writeHash({view:r.id,person:null,event:null,place:null,detail:null});return;
  }
  const execute=()=>{commandRows=null;commandRowsMode='';executeEntityCommand(r);};
  if(typeof window.__MING_ENSURE_ENTITY_DATA==='function'){
    window.__MING_ENSURE_ENTITY_DATA(r.kind,'command-result:'+r.kind,r.id).then(execute).catch(err=>{
      if(typeof failBar==='function')failBar('entity-data','实体数据加载失败：'+String((err&&err.message)||err),{level:'error',retry:()=>location.reload(),retryLabel:'重新加载'});
    });
    return;
  }
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
    return _sub_once(
        text,
        r"function runCommand\(r\)\{.*?\n}\nfunction ensureCommandTrigger",
        run_block,
        "run command",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 V9 人物详情分片钩子到 experience.js")
    parser.add_argument("--check", action="store_true", help="只检查，不写入")
    args = parser.parse_args(argv)
    source = TARGET.read_text(encoding="utf-8")
    updated = render_source(source)
    if updated == source:
        print("V9 人物详情分片命令钩子已同步")
        return 0
    if args.check:
        print("V9 人物详情分片命令钩子未同步；请运行 python src/sync_lazy_data.py")
        return 1
    TARGET.write_text(updated, encoding="utf-8")
    print("V9 人物详情分片命令钩子已写入 experience.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
