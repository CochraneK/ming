# -*- coding: utf-8 -*-
"""兼容旧 V9 命令面板钩子；Classic UI 下保持 no-op。

历史上本脚本会把实体分片加载钩子写入 V3 experience.js 的命令面板。
Classic UI 已主动撤掉可见命令面板，因此现代实体分片由 data-loader.js / lazy-data.js
独立负责；此脚本在 Classic UI 源上应幂等返回，不再强制恢复旧 UI。
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
CLASSIC_MARKER = "Classic UI mode."


def _sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise SystemExit("V9 分片命令钩子锚点异常（%s）：匹配 %d 处" % (label, count))
    return updated


def render_source(source: str) -> str:
    # Classic UI 不再提供命令面板；实体分片逻辑已经完全位于 loader/gate，
    # 因此这里必须 no-op，不能为了历史同步器重新注入可见 UI。
    if CLASSIC_MARKER in source:
        return source
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
    parser = argparse.ArgumentParser(description="同步历史命令面板实体分片钩子；Classic UI 下 no-op")
    parser.add_argument("--check", action="store_true", help="只检查，不写入")
    args = parser.parse_args(argv)
    source = TARGET.read_text(encoding="utf-8")
    updated = render_source(source)
    if updated == source:
        print("实体详情分片钩子已满足当前 UI 模式")
        return 0
    if args.check:
        print("V9 人物详情分片命令钩子未同步；请运行 python src/sync_lazy_data.py")
        return 1
    TARGET.write_text(updated, encoding="utf-8")
    print("V9 人物详情分片命令钩子已写入 experience.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
