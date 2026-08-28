#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本反查补全人物章节出场记录。

背景：LLM 逐章抽取时人物覆盖不全——诊断显示 74/156 章存在「已知人物在正文中高频出现、
但该章抽取结果未登记」的缺口（如靖难主战场章漏掉平安/瞿能/邱福，万历朝章漏掉朱翊钧）。

本脚本对每章正文扫描全部已知人物指称（规范名+别名），采用最长匹配（避免「李善」误吃
「李善长」的前缀伪影），出现 >= THRESHOLD 次者登记为该章出场。

产物：data/derived_chapter_persons.json
  { "_comment": ..., "threshold": 6, "derived": { "朱棣": ["p1-c26", ...], ... } }

说明：
- 只为「已有人物卡」补出场记录，不新建卡；新人物发现属另一任务。
- 输出由 merge.py 消费：并入 character["chapters"]，同时另存 character["chapters_derived"]
  以保源透明（抽取 vs 文本反查 可区分）。
- 书籍原文（明朝那些事儿.txt）为盗版扫描件，仅本地分析，绝不发布。
"""
import json
import os
import re
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(BASE, "明朝那些事儿.txt")
CHAPTERS = os.path.join(BASE, "data", "chapters.json")
DATA = os.path.join(BASE, "data", "data.json")
OUT = os.path.join(BASE, "data", "derived_chapter_persons.json")

THRESHOLD = 6          # 本章出现次数阈值（次）
MIN_NAME_LEN = 2       # 指称最小长度
MAX_GROUP = 120        # 正则 alternation 分组大小

# 泛称/职衔：出现在文中但不指向特定人物，一律排除
GENERIC = {
    "知县", "皇后", "太子", "都督", "太监", "皇帝", "王爷", "大臣", "将军", "尚书",
    "御史", "贵妃", "太后", "藩王", "总兵", "参将", "游击", "指挥", "知府", "郎中",
    "员外", "主事", "锦衣卫", "宦官", "文官", "武将", "官员", "百姓", "皇子", "公主",
    "驸马", "国公", "侯爷", "伯爷", "老师", "皇帝陛下", "副将", "副总兵", "千户",
    "百户", "知州", "巡抚", "总督", "吏部尚书", "给事中", "皇长子", "皇三子",
    "大混混", "朝鲜国王", "燕王", "宁王", "建文帝", "魏公公", "袁督师", "张先生",
}


def keynum(key):
    m = re.match(r"p(\d+)-c(\d+)", key)
    return (int(m.group(1)), int(m.group(2))) if m else (99, 99)


def main():
    book = open(BOOK, encoding="utf-8", errors="ignore").read()
    data = json.load(open(DATA, encoding="utf-8"))
    chapters = [c for c in json.load(open(CHAPTERS, encoding="utf-8"))
                if re.match(r"p\d+-c\d+", c.get("key", ""))]
    chapters.sort(key=lambda c: keynum(c["key"]))

    # 书内章节切分（顺序与 chapters.json 已验证逐位一致 156/156）
    heads = list(re.finditer(r"第[一二三四五六七八九十百]+章[^\n]{0,40}", book))
    if len(heads) != len(chapters):
        raise SystemExit(f"书内标题数 {len(heads)} != 章节数 {len(chapters)}，中止")
    norm = lambda s: re.sub(r"[\s：:！!？?，,。·—\-（）()]", "", s)
    texts = []
    for i, h in enumerate(heads):
        if norm(h.group(0)) != norm(chapters[i]["title"]):
            raise SystemExit(f"第 {i} 位标题不一致：书={h.group(0)!r} vs 索引={chapters[i]['title']!r}，中止")
        end = heads[i + 1].start() if i + 1 < len(heads) else len(book)
        texts.append(norm(book[h.start():end]))

    # 全部指称 -> 规范名（来自 data.json 人物卡，含别名）
    alias2canon = {}
    for c in data["characters"]:
        alias2canon[c["name"]] = c["name"]
        for a in c.get("aliases", []):
            alias2canon.setdefault(a, c["name"])
    terms = sorted(
        (t for t in alias2canon if len(t) >= MIN_NAME_LEN and t not in GENERIC),
        key=len, reverse=True)  # 长名优先，配合逐位置最长匹配

    groups = [terms[i:i + MAX_GROUP] for i in range(0, len(terms), MAX_GROUP)]

    # 逐章扫描：收集所有 (start, end, term)，同位置取最长，再统计规范名
    derived = defaultdict(list)
    per_chapter_stats = {}
    for ci, text in enumerate(texts):
        spans = []  # (start, end, canon)
        for g in groups:
            pat = re.compile("|".join(re.escape(t) for t in g))
            for m in pat.finditer(text):
                spans.append((m.start(), m.end(), alias2canon.get(m.group(0), m.group(0))))
        # 同起点取最长匹配
        spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        counts = defaultdict(int)
        last_end = -1
        for s, e, canon in spans:
            if s < last_end:      # 与更长匹配重叠，丢弃
                continue
            last_end = e
            counts[canon] += 1
        key = chapters[ci]["key"]
        got = [p for p, n in counts.items() if n >= THRESHOLD]
        per_chapter_stats[key] = {"persons": len(got), "candidates": len(counts)}
        for p in got:
            derived[p].append(key)

    # 排除本章本来就已抽取的（对比抽取原始数据无必要：merge 时会去重）
    out = {
        "_comment": ("文本反查推导的人物章节出场（source=文本反查）。对每章正文用最长匹配扫描全部"
                     "已知指称（规范名+别名），出现次数达阈值者登记为该章出场。只为已有人物卡补记录，"
                     "不新建卡；由 src/derive_coverage.py 生成，merge.py 并入 character.chapters "
                     "并另存 chapters_derived 以区分抽取与推导。"),
        "threshold": THRESHOLD,
        "generated_from": "明朝那些事儿.txt（本地，不发布）",
        "chapters_covered": len(texts),
        "derived": {k: sorted(v) for k, v in sorted(derived.items())},
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(len(v) for v in derived.values())
    print(f"文本反查完成：{len(texts)} 章 · 阈值 {THRESHOLD} 次")
    print(f"  涉及人物 {len(derived)} 人 · 补充出场记录 {total} 人×章 -> {os.path.relpath(OUT, BASE)}")
    top = sorted(derived.items(), key=lambda kv: -len(kv[1]))[:8]
    print("  补全最多:", ", ".join(f"{k}+{len(v)}章" for k, v in top))


if __name__ == "__main__":
    main()
