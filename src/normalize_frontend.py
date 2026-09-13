# -*- coding: utf-8 -*-
"""收敛前端里已确认的静态数据口径，防止最终模型变化后页面文案漂移。"""
from __future__ import annotations

import argparse
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
APP = BASE / "web" / "js" / "app.js"

OLD = "基于《明朝那些事儿》知识图谱（156 章 · 1231 人物 · 581 地点 · 1106 事件 · 2324 关系）"
NEW = "基于《明朝那些事儿》知识图谱（${metrics.chapters} 章 · ${metrics.characters} 人物 · ${metrics.locations} 地点 · ${metrics.events} 事件 · ${metrics.relations} 关系）"


def normalize(text: str) -> str:
    if OLD in text:
        if text.count(OLD) != 1:
            raise ValueError("旧洞察统计口径出现次数异常")
        return text.replace(OLD, NEW, 1)
    if NEW in text:
        return text
    raise ValueError("未找到预期的洞察统计口径锚点")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="规范化前端动态统计口径")
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    text = APP.read_text(encoding="utf-8")
    updated = normalize(text)
    if updated == text:
        print("前端动态统计口径已规范化")
        return 0
    if args.check:
        print("前端仍含静态旧统计；请运行 python src/normalize_frontend.py")
        return 1
    APP.write_text(updated, encoding="utf-8")
    print("洞察页统计口径已改为读取 metrics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
