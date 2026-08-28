# -*- coding: utf-8 -*-
"""
把 extract_raw.json（逐章抽取的五元组）聚合为单一数据源 data.json：
  - characters / locations / events 跨章去重聚合（章节列表、别名、参与者合并）
  - relations 去重（from+to+rel）
  - 若 data/geo_annotations.json 存在，则把 modern_address/lng/lat/trace_type/status
    按 ancient 名挂到 locations 上（地理痕迹标注）
  - timeline：按 year 排序的事件时间轴
用法: python merge.py
"""
import json, os, re, tempfile

from clean_rules import (
    PERSON_CANON,
    PERSON_CANON_BY_PART,
    LOCATION_CANON,
    RELATION_PAIR_OVERRIDES,
    canon_event_type,
    canon_relation_category,
    clean_arrows,
    clean_location_route,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "data", "extract_raw.json")
GEO = os.path.join(BASE, "data", "geo_annotations.json")
MANUAL = os.path.join(BASE, "data", "manual_relations.json")
PROFILES = os.path.join(BASE, "data", "char_profiles.json")
REIGNS = os.path.join(BASE, "data", "reigns.json")
LIFESPANS = os.path.join(BASE, "data", "lifespans.json")
VOYAGES = os.path.join(BASE, "data", "voyages.json")
OUT = os.path.join(BASE, "data", "data.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def as_list(value):
    """Treat scalar extraction fields as one item instead of iterating chars."""
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, list):
        return [item.strip() if isinstance(item, str) else item for item in value if item not in (None, "")]
    return []


def canonical(name, part_key=None):
    """人名归一：全局别名表 + 歧义封号按部次上下文裁决。"""
    if name in PERSON_CANON_BY_PART:
        return PERSON_CANON_BY_PART[name].get(part_key, name)
    return PERSON_CANON.get(name, name)


def write_json_atomic(path, value):
    directory = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(prefix=".json-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def year_bounds(value):
    """Return numeric year bounds while preserving the original display text."""
    if value is None or value == "":
        return None, None
    years = [int(x) for x in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", str(value))]
    if not years:
        return None, None
    return years[0], years[-1]


def normalize_year(value):
    """纯数字年份归一为 int；保留区间与年号说明文本原样展示。"""
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}", text):
        return int(text)
    return text


# 复合地点中的非地理子项（机构 / 宫禁内部空间），拆分时直接并入主城
LOCATION_SPLIT_STOP = {
    "宫中", "内阁", "礼部", "东厂", "锦衣卫", "三法司", "午门",
    "刑部", "大牢", "诏狱", "南城", "北城",
}


def split_location_fragments(name):
    """把 '甲/乙/丙'、'城·景点'、'甲、乙、丙' 这类复合地点拆成独立古地名，便于分别定位。"""
    if "/" not in name and "·" not in name and "、" not in name:
        return [name]
    fragments = []
    for part in re.split(r"[/·、]", name):
        part = part.strip()
        if not part or part in LOCATION_SPLIT_STOP:
            continue
        fragments.append(part)
    return fragments or [name]

raw = load_json(RAW, [])
geo = {}
if os.path.exists(GEO):
    for g in json.load(open(GEO, encoding="utf-8")):
        geo[g["ancient"]] = g
# 人工增补关系（名臣对/组合），与原始抽取解耦，重跑不丢
manual_rels = load_json(MANUAL, [])
# 角色精校档案（生卒/籍贯），可单独维护，重跑不丢
profiles = load_json(PROFILES, {})
# 帝王在位时段（人工整理的王朝骨架），供报告帝王视图与时间轴年号标注使用
reigns = load_json(REIGNS, [])
# 人物年谱（人工整理生卒年，标注通行史料来源），供报告年谱视图使用
lifespans = load_json(LIFESPANS, [])
# 郑和下西洋示意航线停靠点（按书中叙述整理），供地图航线叠加使用
voyages = load_json(VOYAGES, {})

characters, locations, events = {}, {}, {}
relations = []
for mr in manual_rels:
    chapter = mr.get("chapter") or "curated"
    relations.append({"from": canonical(mr["from"]), "to": canonical(mr["to"]),
                      "rel": clean_arrows(mr["rel"]), "chapter": chapter})

merged_person_names = set()
merged_location_groups = {}
selfloop_dropped = 0

for ch in raw:
    k = ch["key"]
    part_key = k.split("-", 1)[0]
    for c in ch.get("characters", []):
        original_name = c["name"]
        n = canonical(original_name, part_key)
        if original_name != n:
            merged_person_names.add(original_name)
        d = characters.setdefault(n, {"name": n, "role": "", "faction": "", "aliases": [], "chapters": []})
        d["role"] = d["role"] or clean_arrows(c.get("role", ""))
        d["faction"] = d["faction"] or clean_arrows(c.get("faction", ""))
        # 精校档案覆盖生卒/籍贯/职务（若有）
        profile = profiles.get(original_name) or profiles.get(n)
        if profile:
            for f in ("life", "birth", "role_clean"):
                if profile.get(f):
                    d[f] = profile[f]
        if original_name != n and original_name not in d["aliases"]:
            d["aliases"].append(original_name)
        for a in as_list(c.get("aliases", [])):
            if a and a not in d["aliases"]:
                d["aliases"].append(a)
        if k not in d["chapters"]:
            d["chapters"].append(k)
    for l in ch.get("locations", []):
        original_ancient = l["ancient"]
        canonical_fragments = []
        for fragment in split_location_fragments(original_ancient):
            canonical_fragments.append(LOCATION_CANON.get(fragment, fragment))
        canonical_fragments = list(dict.fromkeys(canonical_fragments))
        for n in canonical_fragments:
            if n != original_ancient:
                merged_location_groups.setdefault(n, set()).add(original_ancient)
            d = locations.setdefault(n, {"ancient": n, "mentioned_as": [], "chapters": []})
            if original_ancient != n and original_ancient not in d["mentioned_as"]:
                d["mentioned_as"].append(original_ancient)
            for m in as_list(l.get("mentioned_as", [])):
                if m not in d["mentioned_as"]:
                    d["mentioned_as"].append(m)
            if k not in d["chapters"]:
                d["chapters"].append(k)
            geo_source = geo.get(n) or geo.get(original_ancient)
            if geo_source:
                for f in ("modern_address", "lng", "lat", "trace_type", "status", "note"):
                    if f in geo_source and f not in d:
                        d[f] = geo_source[f]
    for e in ch.get("events", []):
        n = e["name"]
        d = events.setdefault(n, {"name": n, "type": "", "participants": [], "location": "", "year": "", "chapters": []})
        d["type"] = d["type"] or e.get("type", "")
        event_location = e.get("location", "")
        d["location"] = d["location"] or clean_location_route(event_location)
        d["year"] = d["year"] or e.get("year", "")
        for p in as_list(e.get("participants", [])):
            normalized = canonical(p, part_key)
            if normalized not in d["participants"]:
                d["participants"].append(normalized)
        if k not in d["chapters"]:
            d["chapters"].append(k)
    for r in ch.get("relations", []):
        relations.append({"from": canonical(r["from"], part_key), "to": canonical(r["to"], part_key),
                          "rel": clean_arrows(r["rel"]), "chapter": k})

# 年份归一（纯数字转 int）与事件归一类别（类型 + 事件名双重判定）
for name, e in events.items():
    e["year"] = normalize_year(e["year"])
    e["category"] = canon_event_type(e.get("type", ""), name)

seen, rels = set(), []
character_names = set(characters.keys())
for r in relations:
    if r["from"] == r["to"]:
        selfloop_dropped += 1
        continue
    key = (r["from"], r["to"], r["rel"])
    if key in seen:
        continue
    seen.add(key)
    category = canon_relation_category(r["rel"])
    if r["from"] not in character_names or r["to"] not in character_names:
        category = "地点关联"
    override = RELATION_PAIR_OVERRIDES.get((r["from"], r["to"]))
    if override:
        category = override
    rels.append({**r, "category": category})

timeline = []
for n, e in events.items():
    year_start, year_end = year_bounds(e["year"])
    timeline.append({"name": n, "year": e["year"], "year_start": year_start, "year_end": year_end,
                     "type": e["type"], "category": e["category"], "location": e["location"],
                     "participants": e.get("participants", []), "chapters": e["chapters"]})
timeline.sort(key=lambda x: (
    x["year_start"] is None,
    x["year_start"] if x["year_start"] is not None else 9999,
    x["year_end"] if x["year_end"] is not None else 9999,
    x["name"],
))

relation_category_counts = {}
for r in rels:
    relation_category_counts[r["category"]] = relation_category_counts.get(r["category"], 0) + 1
event_category_counts = {}
for e in events.values():
    event_category_counts[e["category"]] = event_category_counts.get(e["category"], 0) + 1

data = {
    "characters": list(characters.values()),
    "locations": list(locations.values()),
    "events": list(events.values()),
    "relations": rels,
    "timeline": timeline,
    "reigns": reigns,
    "lifespans": lifespans,
    "voyages": voyages,
    "meta": {"source_chapters": len(raw), "geo_annotated": len(geo),
             "located_locations": sum(1 for l in locations.values()
                                       if l.get("lng") is not None and l.get("lat") is not None),
             "cleaning": {
                 "person_merges": len(merged_person_names),
                 "person_merged_names": sorted(merged_person_names),
                 "location_merge_groups": {k: sorted(v) for k, v in sorted(merged_location_groups.items())},
                 "selfloop_dropped": selfloop_dropped,
                 "relation_categories": dict(sorted(relation_category_counts.items(), key=lambda kv: -kv[1])),
                 "event_categories": dict(sorted(event_category_counts.items(), key=lambda kv: -kv[1])),
             }},
}
write_json_atomic(OUT, data)
located = sum(1 for l in data["locations"] if l.get("lng") is not None)
print(f"已聚合 -> data.json")
print(f"  角色 {len(data['characters'])} | 地点 {len(data['locations'])}（已标坐标 {located}）| 事件 {len(data['events'])} | 关系 {len(data['relations'])} | 时间轴 {len(data['timeline'])}")
print(f"  来源章 {len(raw)} | 地理标注 {len(geo)} 条")
cleaning = data["meta"]["cleaning"]
print(f"  清洗：人物别名合并 {cleaning['person_merges']} 个 | 地点同城合并 {len(cleaning['location_merge_groups'])} 组 | 自环剔除 {cleaning['selfloop_dropped']} 条")
