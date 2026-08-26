# -*- coding: utf-8 -*-
"""按 key 列表打印 chapters.json 中若干章的正文，供抽取使用。
用法: python dump_chapters.py p1-c1 p1-c2 ...
"""
import json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = os.path.join(BASE, "data", "chapters.json")
data = json.load(open(CH, encoding="utf-8"))
idx = {e["key"]: e for e in data}

keys = sys.argv[1:]
for k in keys:
    e = idx.get(k)
    if not e:
        print(f"\n[!! 未找到 {k}]")
        continue
    print(f"\n========== {k} | {e['title']} | {e['part_title']} ==========")
    print(e["body"])
