# -*- coding: utf-8 -*-
"""V12：让事件索引使用 sourceCount，而不是要求完整 sources 数组常驻。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TARGET = BASE / "web" / "js" / "app.js"
OLD = "${x.sources.length}章"
NEW = "${x.sourceCount!=null?x.sourceCount:(x.sources||[]).length}章"


def render_source(source: str) -> str:
    if NEW in source:
        return source
    count = source.count(OLD)
    if count != 1:
        raise RuntimeError("V12 事件来源计数锚点异常：%d" % count)
    return source.replace(OLD, NEW, 1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 V12 事件摘要 sourceCount 兼容")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    source = TARGET.read_text(encoding="utf-8")
    try:
        updated = render_source(source)
    except RuntimeError as exc:
        print("[FAIL] %s" % exc, file=sys.stderr)
        return 2
    if updated == source:
        print("V12 事件摘要前端钩子已同步")
        return 0
    if args.check:
        print("V12 事件摘要前端钩子尚未同步", file=sys.stderr)
        return 1
    TARGET.write_text(updated, encoding="utf-8")
    print("V12 事件摘要前端钩子已写入")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
