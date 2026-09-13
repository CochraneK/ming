# -*- coding: utf-8 -*-
"""把 V5 lazy-data 钩子安全写入 V3 experience.js。

experience.js 仍是全局搜索/首页叙事/图谱阅读器的人工维护源。本脚本只做三处精确变换：
1) 搜索索引缓存区分 boot / full；2) full 到达后重建索引；3) 打开全局搜索时主动请求 full。
采用锚点 + 幂等标记，避免重写整份前端文件。
"""
from __future__ import annotations

import argparse
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TARGET = BASE / "web" / "js" / "experience.js"
MARKER = "/* V5_LAZY_COMMAND_DATA */"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit("V5 lazy-data 锚点异常（%s）：匹配 %d 处" % (label, count))
    return text.replace(old, new, 1)


def render_source(source: str) -> str:
    if MARKER in source:
        return source

    text = source
    text = _replace_once(
        text,
        "let commandRows=null,commandResults=[],commandActive=0,commandLastFocus=null;",
        MARKER + "\nlet commandRows=null,commandRowsFull=false,commandResults=[],commandActive=0,commandLastFocus=null;",
        "command state",
    )
    text = _replace_once(
        text,
        "function buildCommandRows(){\n  if(commandRows)return commandRows;\n  const rows=[];",
        "function commandHasFullData(){return typeof window.__MING_ENSURE_FULL_DATA!=='function'||window.__MING_FULL_DATA_READY===true;}\n"
        "function buildCommandRows(){\n  const full=commandHasFullData();\n  if(commandRows&&commandRowsFull===full)return commandRows;\n  const rows=[];",
        "build command rows",
    )
    text = _replace_once(
        text,
        "  commandRows=rows;\n  return rows;\n}",
        "  commandRows=rows;commandRowsFull=full;\n  return rows;\n}",
        "command cache mode",
    )
    text = _replace_once(
        text,
        "  const input=shell.querySelector('#commandInput');input.value=seed||'';commandActive=0;renderCommand(input.value);requestAnimationFrame(()=>input.focus());",
        "  const input=shell.querySelector('#commandInput');input.value=seed||'';commandActive=0;renderCommand(input.value);\n"
        "  if(!commandHasFullData()&&typeof window.__MING_ENSURE_FULL_DATA==='function'){\n"
        "    window.__MING_ENSURE_FULL_DATA('command').then(()=>{commandRows=null;renderCommand(input.value);}).catch(err=>{\n"
        "      const host=document.getElementById('commandResults');if(host)host.innerHTML='<div class=\"command-empty\">完整知识库加载失败，可稍后重试。</div>';\n"
        "      if(typeof failBar==='function')failBar('full-data','完整知识库加载失败：'+String((err&&err.message)||err),{level:'error',retry:()=>location.reload(),retryLabel:'重新加载'});\n"
        "    });\n"
        "  }\n"
        "  requestAnimationFrame(()=>input.focus());",
        "open command lazy load",
    )
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 V5 lazy-data 钩子到 experience.js")
    parser.add_argument("--check", action="store_true", help="只检查，不写入")
    args = parser.parse_args(argv)
    source = TARGET.read_text(encoding="utf-8")
    updated = render_source(source)
    if updated == source:
        print("V5 lazy-data 钩子已同步")
        return 0
    if args.check:
        print("V5 lazy-data 钩子未同步；请运行 python src/sync_lazy_data.py")
        return 1
    TARGET.write_text(updated, encoding="utf-8")
    print("V5 lazy-data 钩子已写入 experience.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
