# -*- coding: utf-8 -*-
# 按章节 key 导出正文，供抽取 agent 读取。用法: python src/_dump_chapter.py p2-c2
import json, sys, os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = os.path.join(BASE, "data", "chapters.json")
if len(sys.argv) != 2:
    raise SystemExit("用法：python src/_dump_chapter.py <chapter-key>")
k = sys.argv[1]
ch = json.load(open(CH, encoding="utf-8"))
e = next((x for x in ch if x.get("key") == k), None)
if not e:
    print("NOTFOUND", k); sys.exit(1)
print("PART:", e.get("part_title", ""))
print("CHAPTER:", e.get("chapter_title", ""))
print("KEY:", e.get("key", ""))
print("BODY_START")
print(e.get("body", ""))
print("BODY_END")
