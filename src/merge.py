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
MANUAL_YEARS = os.path.join(BASE, "data", "manual_event_years.json")
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
# 人工补年：未知年份事件回填（来源=记忆/推导），与原始抽取解耦，重跑不丢
manual_years = load_json(MANUAL_YEARS, {})
# 角色精校档案（生卒/籍贯），可单独维护，重跑不丢
profiles = load_json(PROFILES, {})
# 帝王在位时段（人工整理的王朝骨架），供报告帝王视图与时间轴年号标注使用
reigns = load_json(REIGNS, [])
# 人物年谱（人工整理生卒年，标注通行史料来源），供报告年谱视图使用
lifespans = load_json(LIFESPANS, [])
# 年谱补录（源=记忆/通用明史）：并入 lifespans，重跑不丢；不覆盖已有条目。
# 生年不详者用「卒年 - 估值」占位并标 life_estimated，报告端以虚线条区分，绝不冒充已知年份。
MANUAL_LIFESPANS = os.path.join(BASE, "data", "manual_lifespans.json")
MANUAL_PERSONS = os.path.join(BASE, "data", "manual_persons.json")
ESTIMATED_SPAN = 55
lifespan_added = 0
for _ml in (load_json(MANUAL_LIFESPANS, {}).get("entries") or []):
    if not _ml.get("name") or any(x["name"] == _ml["name"] for x in lifespans):
        continue
    entry = {
        "name": _ml["name"],
        "group": _ml.get("group") or "文苑行者",
        "birth": _ml.get("birth"),
        "death": _ml.get("death"),
        "note": _ml.get("note", ""),
        "approx": bool(_ml.get("approx")),
        "source": "记忆",
    }
    if entry["birth"] is None and entry["death"] is not None:
        entry["birth"] = entry["death"] - ESTIMATED_SPAN
        entry["life_estimated"] = True
        entry["approx"] = True
    lifespans.append(entry)
    lifespan_added += 1
# 郑和下西洋示意航线停靠点（按书中叙述整理），供地图航线叠加使用
voyages = load_json(VOYAGES, {})

characters, locations, events = {}, {}, {}
relations = []

# 人工补录人物（源=书本提及+通用明史，与逐章抽取解耦，重跑不丢，不覆盖已抽取同名卡）
for _mp in (load_json(MANUAL_PERSONS, {}).get("entries") or []):
    _n = _mp.get("name")
    if not _n or _n in characters:
        continue
    characters[_n] = {
        "name": _n,
        "role": _mp.get("role", ""),
        "faction": _mp.get("faction", ""),
        "aliases": list(_mp.get("aliases", [])),
        "chapters": list(_mp.get("chapters", [])),
        "life": _mp.get("life", ""),
        "birth": _mp.get("birth", ""),
        "source": _mp.get("source", "人工补录"),
    }
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

# 人工补年：仅回填抽取阶段未给年份的事件，写入来源标记，尊重源透明度
if manual_years:
    for name, e in events.items():
        my = manual_years.get(e["name"])
        if my and e.get("year") in ("", None):
            e["year"] = normalize_year(my["year"])
            e["year_source"] = my.get("source", "记忆")
            if my.get("approx"):
                e["year_approx"] = True
            if my.get("note"):
                e["year_note"] = my["note"]

# ===== 人工勘误（data/manual_corrections.json）：重跑 merge 不丢，覆盖抽取结果 =====
CORRECTIONS = load_json(os.path.join(BASE, "data", "manual_corrections.json"), {})

# 1) 事件年份勘误（源=记忆/通用明史，写入 year_source 保持源透明）
for _name, _c in (CORRECTIONS.get("event_years") or {}).items():
    _e = events.get(_name)
    if _e is None:
        continue
    _e["year"] = normalize_year(_c["year"])
    _e["year_source"] = _c.get("source", "记忆")
    if _c.get("approx"):
        _e["year_approx"] = True
    if _c.get("note"):
        _e["year_note"] = _c["note"]
    _e["year_corrected"] = True

# 2) 人物卡勘误：剔除误挂别名（不同人错当同一人）+ 势力 / 身份勘误
for _name, _bad in (CORRECTIONS.get("character_alias_remove") or {}).items():
    _c = characters.get(_name)
    if _c:
        _c["aliases"] = [a for a in _c.get("aliases", []) if a not in _bad]
for _name, _faction in (CORRECTIONS.get("character_faction") or {}).items():
    if _name in characters:
        characters[_name]["faction"] = _faction
        characters[_name]["faction_source"] = "记忆"
for _name, _role in (CORRECTIONS.get("character_role") or {}).items():
    if _name in characters:
        characters[_name]["role"] = _role
        characters[_name]["role_source"] = "记忆"

# 3) 同一人物被切成多张卡 -> 并入规范名（别名 / 章节 / 事件合并）
def merge_character_cards(src, dst):
    s, d = characters.get(src), characters.get(dst)
    if s is None or d is None or src == dst:
        return False
    aliases = set(d.get("aliases", [])) | set(s.get("aliases", [])) | {src}
    aliases.discard(dst)
    d["aliases"] = sorted(aliases)
    d["chapters"] = sorted(set(d.get("chapters", [])) | set(s.get("chapters", [])))
    if not d.get("faction") and s.get("faction"):
        d["faction"] = s["faction"]
    if not d.get("life") and s.get("life"):
        d["life"] = s["life"]
    if not d.get("birth") and s.get("birth"):
        d["birth"] = s["birth"]
    if len(s.get("role", "")) > len(d.get("role", "")):
        d["role"] = s["role"]
    del characters[src]
    return True

person_card_merges = []
for _card, _canon in (CORRECTIONS.get("character_merges") or {}).items():
    if merge_character_cards(_card, _canon):
        person_card_merges.append(f"{_card}→{_canon}")

# 合并后关系端点同步改指规范名，避免出现指向已删除卡的悬空关系
_char_merges = CORRECTIONS.get("character_merges") or {}
for r in relations:
    for _k in ("from", "to"):
        if r.get(_k) in _char_merges:
            r[_k] = _char_merges[r[_k]]

# 4) 地点勘误（今址等）
for _name, _fix in (CORRECTIONS.get("location_fixes") or {}).items():
    _l = locations.get(_name)
    if _l:
        _l.update(_fix)

# 5) 关系勘误：亲属关系统一为「长辈 → 晚辈」；剔除矛盾重复与跨代错配
_rel_fix = CORRECTIONS.get("relation_fixes") or {}
rel_flipped = 0
rel_dropped_fix = 0
for _f in (_rel_fix.get("flip") or []):
    for r in relations:
        if r["from"] == _f["from"] and r["to"] == _f["to"] and r["rel"] == _f["rel"]:
            r["from"], r["to"] = r["to"], r["from"]
            r["rel_corrected"] = "方向归一为长辈→晚辈"
            rel_flipped += 1
_drop_keys = {(d["from"], d["to"], d["rel"]) for d in (_rel_fix.get("drop") or [])}
_before = len(relations)
relations = [r for r in relations if (r["from"], r["to"], r["rel"]) not in _drop_keys]
rel_dropped_fix = _before - len(relations)

# 6) 文本反查补全人物出场（data/derived_chapter_persons.json，source=文本反查）：
#    LLM 逐章抽取对人物覆盖不全，此处按「正文出现>=阈值次」补登记，抽取章在前、推导章在后，
#    chapters_derived 单独保存以保源透明（报告端可区分）。
DERIVED_COVER = load_json(os.path.join(BASE, "data", "derived_chapter_persons.json"), {})
_derived = DERIVED_COVER.get("derived") or {}
coverage_added = 0
for _name, _chs in _derived.items():
    _c = characters.get(_name)
    if _c is None:
        continue
    _extra = [k for k in _chs if k not in _c["chapters"]]
    if _extra:
        _c["chapters"] = _c["chapters"] + _extra
        _c.setdefault("chapters_derived", []).extend(_extra)
        coverage_added += len(_extra)

seen, rels = set(), []
character_names = set(characters.keys())
location_names = set(locations.keys())

# 关系端点类型判定：人物 / 地点 / 派系机构 / 其他。
# 历史遗留：只要端点不是人物就被笼统打成「地点关联」，把东林党、浙党、阉党、后金、
# 东厂这类派系/机构/政权误标成地点。改为按「人物优先 → 地点 → 机构派系 → 其他」判定。
# 政权（朝代/朝廷）：与「派系机构」分开，避免把元朝、清廷标成机构。
REGIME_EXACT = {"元朝", "明朝", "清朝", "清廷", "北元", "后金", "大顺", "大西", "西夏", "大理"}
# 派系/机构：注意不要收录会误伤人名的后缀（如「监」，会把「太监」误判成机构）。
ORG_EXACT = {"东厂", "西厂", "内厂", "锦衣卫", "东林党", "浙党", "阉党", "齐楚浙三党",
             "宣党", "昆党", "楚党", "齐党", "秦党"}
ORG_SUFFIXES = ("党", "厂", "司", "卫", "所", "营", "军", "部", "府", "局", "门",
                "会", "社", "教", "国", "寺", "观", "院", "阁", "省", "道")


def _endpoint_kind(name):
    """判断单个关系端点的类型。人物优先，避免与地点/机构重名时误判。"""
    if name in character_names:
        return "person"
    if name in location_names:
        return "place"
    if name in REGIME_EXACT:
        return "regime"
    if name in ORG_EXACT or name.endswith(ORG_SUFFIXES):
        return "org"
    # 兜底：带「军」的军事实体（如「清军（皇太极）」因结尾是括号无法走后缀匹配）
    if "军" in name:
        return "org"
    return "other"


for r in relations:
    if r["from"] == r["to"]:
        selfloop_dropped += 1
        continue
    key = (r["from"], r["to"], r["rel"])
    if key in seen:
        continue
    seen.add(key)
    category = canon_relation_category(r["rel"])
    kf, kt = _endpoint_kind(r["from"]), _endpoint_kind(r["to"])
    if kf != "person" or kt != "person":
        # 至少一个端点不是人物：按非人物端点里最具体的类型归类
        kinds = {kf, kt}
        if "place" in kinds:
            category = "地点关联"
        elif "org" in kinds:
            category = "派系机构关联"
        elif "regime" in kinds:
            category = "政权关联"
        else:
            category = "其他实体关联"
    override = RELATION_PAIR_OVERRIDES.get((r["from"], r["to"]))
    if override:
        category = override
    rels.append({**r, "category": category, "endpoint_kind": {"from": kf, "to": kt}})

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
                 "person_card_merges": person_card_merges,
                 "corrections": {
                     "event_years": len(CORRECTIONS.get("event_years") or {}),
                     "character_faction": len(CORRECTIONS.get("character_faction") or {}),
                     "character_role": len(CORRECTIONS.get("character_role") or {}),
                     "location_fixes": len(CORRECTIONS.get("location_fixes") or {}),
                     "relation_flipped": rel_flipped,
                     "relation_dropped": rel_dropped_fix,
                     "lifespan_added": lifespan_added,
                     "coverage_added": coverage_added,
                 },
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
