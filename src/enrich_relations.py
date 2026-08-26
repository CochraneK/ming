# -*- coding: utf-8 -*-
"""
关系补全（长尾改进 ④）：
  1) 按 relations 列表正确计算“孤立角色”（未出现在任何关系的 from/to 中）。
  2) 对高频/头部角色（章节数>=4），用“同一事件共现”推导关系，rel 标“同事件（推导）”，
     写入 data/manual_relations.json（人工增补层，merge 后保留，不覆盖原抽取）。
用法: python enrich_relations.py
"""
import json, os
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data", "data.json")
MANUAL = os.path.join(BASE, "data", "manual_relations.json")

d = json.load(open(DATA, encoding="utf-8"))
chars = {c["name"]: c for c in d["characters"]}
rels = d["relations"]
names = set(chars)

# 正确孤立率：出现在任何关系 from/to 的角色
linked = set()
for r in rels:
    if r["from"] in names:
        linked.add(r["from"])
    if r["to"] in names:
        linked.add(r["to"])
isolated_before = [n for n in names if n not in linked]
print(f"角色总数 {len(names)} | 已关联 {len(linked)} | 孤立(正确口径) {len(isolated_before)} ({len(isolated_before)/len(names)*100:.1f}%)")

# 头部角色阈值
PROM = 4
prom = {n for n, c in chars.items() if len(c.get("chapters", [])) >= PROM}
print(f"头部角色(章数>={PROM}): {len(prom)}")

# 已存在的关系对（避免重复追加）
existing = {(r["from"], r["to"], r["rel"]) for r in rels}
manual = json.load(open(MANUAL, encoding="utf-8")) if os.path.exists(MANUAL) else []
existing |= {(m["from"], m["to"], m["rel"]) for m in manual}

new_rels = []
seen_local = set()
for e in d["events"]:
    parts = [p for p in e.get("participants", []) if p in names]
    # 只取头部角色之间的共现，降低噪声
    head_parts = [p for p in parts if p in prom]
    for i in range(len(head_parts)):
        for j in range(i + 1, len(head_parts)):
            a, b = head_parts[i], head_parts[j]
            key = (a, b, "同事件（推导）")
            if key in existing or key in seen_local:
                continue
            seen_local.add(key)
            new_rels.append({"from": a, "to": b, "rel": "同事件（推导）", "chapter": "推导"})

manual.extend(new_rels)
json.dump(manual, open(MANUAL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"新增推导关系: {len(new_rels)}（写入 manual_relations.json）")

# 估算重跑后孤立率下降（基于新增关系涉及的头部角色）
new_linked = set()
for r in new_rels:
    new_linked.add(r["from"]); new_linked.add(r["to"])
isolated_after_est = [n for n in isolated_before if n not in new_linked]
print(f"预计重跑后孤立(头部相关): {len(isolated_after_est)}（其中头部角色减少 {len([n for n in new_linked if n in isolated_before])}）")
