# -*- coding: utf-8 -*-
"""Generate the static knowledge report from data/data.json.

The report is deliberately generated from one source so that the full-book and
part-one outputs cannot drift.  It is a static HTML artifact with lazy client
rendering; no build tool or third-party Python package is required.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import sys
from pathlib import Path

from clean_rules import EVENT_CATEGORIES, RELATION_CATEGORIES, canon_event_type, canon_relation_category


BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "data.json"
RAW_PATH = BASE / "data" / "extract_raw.json"
CHAPTERS_PATH = BASE / "data" / "chapters.json"
OUT_PATH = BASE  # 报告直接输出到项目根：index.html（全书，唯一入口）

# 人名归一与 merge.py 共用同一份规则；data.json 已在聚合时归一，这里是双保险
from clean_rules import PERSON_CANON, PERSON_CANON_BY_PART
CANON = PERSON_CANON
# 跨学科洞察报告内容模块（与 generate_report.py 同目录）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from insight_content import INSIGHT_SECTIONS, INSIGHT_REFS
    INSIGHT_PAYLOAD = {"sections": INSIGHT_SECTIONS, "refs": INSIGHT_REFS}
except Exception:
    INSIGHT_PAYLOAD = {"sections": [], "refs": []}
# 共享核心：年份解析与经纬度校验必须与 audit_final.py 用同一份实现，
# 否则会出现「审计说 6 个未知年份、报告说 7 个」这类口径漂移。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.year_parser import year_bounds as _shared_year_bounds
PARTS = {
    "p1": "壹部 · 洪武大帝",
    "p2": "贰部 · 万国来朝",
    "p3": "叁部 · 妖孽宫廷",
    "p4": "肆部 · 粉饰太平",
    "p5": "伍部 · 帝国飘摇",
    "p6": "陆部 · 日暮西山",
    "p7": "柒部 · 大结局",
}


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def chapter_key(value: str):
    match = re.match(r"p(\d+)-c(\d+)$", value or "")
    return (int(match.group(1)), int(match.group(2))) if match else (99, 99)


def year_bounds(value):
    """年份解析统一走 src/core/year_parser.py（与 audit_final.py 共用同一真源）。"""
    return _shared_year_bounds(value)


def canonical(name: str) -> str:
    return CANON.get(name, name)


# ---------------------------------------------------------------- 实体 ID（Phase 3）
# 统一 ID 规则：`<类型>:<规范名>`。规范名在最终模型里已保证唯一（审计 R-CHAR-01 强制），
# 所以拼出来的 ID 稳定、可读、可直接用于 URL deep link（#view=characters&person=于谦）。
# 关系 ID 用内容哈希，保证「同一条关系在多次构建中得到同一个 ID」——
# 用下标编号会在数据增删后整体漂移，deep link 就废了。
ENTITY_TYPES = ("person", "place", "org", "regime", "other")


def entity_id(kind: str, name: str) -> str:
    return f"{kind or 'other'}:{name}"


def relation_id(from_name: str, to_name: str, rel: str, source: str) -> str:
    raw = f"{from_name}|{to_name}|{rel}|{source}".encode("utf-8")
    return "relation:" + hashlib.sha1(raw).hexdigest()[:12]


# 派系识别：faction 字段在抽取阶段混进了大量非派系信息（1231 人产生 473 种字符串），
# 这里做一次结构化解析，把真正的派系名挑出来放进 factions 列表，原始串保留在 factionRaw。
FACTION_TOKENS = ("东林党", "东林", "阉党", "浙党", "楚党", "齐党", "宣党", "昆党",
                  "复社", "齐楚浙三党", "邪党", "清流")


def parse_factions(*texts) -> list:
    joined = " ".join(t for t in texts if t)
    found = []
    for token in FACTION_TOKENS:
        if token in joined:
            # 「东林」与「东林党」视为同一派系，统一成「东林党」
            canon_token = "东林党" if token == "东林" else token
            if canon_token not in found:
                found.append(canon_token)
    return found


def region_name(address: str) -> str:
    for keyword, name in (
        ("北京", "北京"), ("河北", "河北"), ("天津", "河北"),
        ("山东", "山东"), ("安徽", "安徽"), ("江苏", "江苏"),
        ("内蒙古", "内蒙古·塞外"), ("云南", "西南"), ("四川", "西南"),
        ("辽宁", "东北"), ("吉林", "东北"), ("山西", "山西"),
        ("甘肃", "西北"), ("宁夏", "西北"), ("陕西", "西北"),
        ("河南", "中原"), ("浙江", "江南"), ("江西", "江南"),
        ("湖北", "中南"), ("广西", "中南"), ("广东", "中南"), ("湖南", "中南"),
        ("上海", "江南"), ("福建", "东南"),
        ("重庆", "西南"), ("贵州", "西南"),
        ("内蒙古", "内蒙古·塞外"), ("蒙古", "塞外"),
        ("朝鲜", "境外"), ("韩国", "境外"), ("日本", "境外"), ("越南", "境外"),
        ("冲绳", "境外"), ("伊拉克", "境外"), ("青海", "西北"), ("新疆", "西北"),
    ):
        if keyword in (address or ""):
            return name
    return "未标注区域"


def chapter_title(key: str, raw_by_key: dict) -> str:
    item = raw_by_key.get(key, {})
    return item.get("chapter") or item.get("title") or key


def source_items(keys, chapter_by_key):
    result = []
    for key in sorted(set(keys), key=chapter_key):
        if key not in chapter_by_key:
            continue
        item = chapter_by_key[key]
        result.append({
            "key": key,
            "title": item["title"],
            "part": item["part"],
        })
    return result


def clean_role(role: str) -> str:
    if not role:
        return "身份待补"
    first = re.split(r"[，。；、]", role, maxsplit=1)[0].strip()
    return first or "身份待补"


def distribution_stats(values):
    """Return comparable population statistics for a chapter-level series."""
    if not values:
        return {
            "count": 0, "mean": 0, "median": 0, "min": 0, "max": 0,
            "p25": 0, "p75": 0, "cv": 0, "zeros": 0,
        }
    ordered = sorted(values)
    count = len(ordered)
    mean = sum(ordered) / count

    def percentile(fraction):
        position = (count - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, count - 1)
        weight = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * weight

    variance = sum((value - mean) ** 2 for value in ordered) / count
    return {
        "count": count,
        "sum": sum(ordered),
        "mean": round(mean, 2),
        "median": round(percentile(0.5), 2),
        "min": ordered[0],
        "max": ordered[-1],
        "p25": round(percentile(0.25), 2),
        "p75": round(percentile(0.75), 2),
        "cv": round((variance ** 0.5) / mean, 3) if mean else 0,
        "zeros": sum(value == 0 for value in ordered),
    }


def build_distribution(raw_by_key, selected_keys, chapter_by_key, chapter_records, metrics):
    """Build raw chapter extraction diagnostics and the source-to-evidence hierarchy."""
    chapter_text = {
        item.get("key"): item.get("body", "")
        for item in chapter_records
        if item.get("type", "") == "chapter"
    }
    chapters = []
    for key in selected_keys:
        raw = raw_by_key.get(key, {})

        def unique_values(items, getter):
            values = {getter(item) for item in items if getter(item)}
            return len(values)

        characters = unique_values(
            raw.get("characters", []),
            lambda item: canonical(item.get("name", "")),
        )
        locations = unique_values(
            raw.get("locations", []),
            lambda item: item.get("ancient", ""),
        )
        events = unique_values(
            raw.get("events", []),
            lambda item: item.get("name", ""),
        )
        relation_keys = {
            (
                canonical(item.get("from", "")),
                canonical(item.get("to", "")),
                item.get("rel", ""),
            )
            for item in raw.get("relations", [])
            if item.get("from") and item.get("to")
        }
        relations = len(relation_keys)
        text_length = len(chapter_text.get(key, ""))
        total = characters + locations + events + relations
        chapters.append({
            "key": key,
            "partKey": key.split("-", 1)[0],
            "part": PARTS.get(key.split("-", 1)[0], chapter_by_key[key]["part"]),
            "title": chapter_by_key[key]["title"],
            "characters": characters,
            "locations": locations,
            "events": events,
            "relations": relations,
            "total": total,
            "textLength": text_length,
            "density": round(total * 10000 / text_length, 2) if text_length else 0,
        })

    dimensions = ("characters", "locations", "events", "relations", "total", "density")
    stats = {dimension: distribution_stats([item[dimension] for item in chapters]) for dimension in dimensions}
    total_extraction = stats["total"]["sum"]
    parts = []
    part_keys = sorted({item["partKey"] for item in chapters}, key=lambda value: int(value[1:]))
    for part_key in part_keys:
        items = [item for item in chapters if item["partKey"] == part_key]
        text_length = sum(item["textLength"] for item in items)
        total = sum(item["total"] for item in items)
        parts.append({
            "partKey": part_key,
            "part": items[0]["part"],
            "chapters": len(items),
            "textLength": text_length,
            "characters": sum(item["characters"] for item in items),
            "locations": sum(item["locations"] for item in items),
            "events": sum(item["events"] for item in items),
            "relations": sum(item["relations"] for item in items),
            "total": total,
            "avgTotal": round(total / len(items), 2) if items else 0,
            "density": round(total * 10000 / text_length, 2) if text_length else 0,
            "share": round(total * 100 / total_extraction, 2) if total_extraction else 0,
        })

    strongest_dimension = max(
        (dimension for dimension in dimensions if dimension != "density"),
        key=lambda dimension: stats[dimension]["cv"],
    )
    max_density = stats["density"]["max"]
    min_density = stats["density"]["min"]
    return {
        "chapters": chapters,
        "parts": parts,
        "stats": stats,
        "judgement": {
            "overall": "存在中等程度的章节差异，地点数和每万字密度的长尾最明显。",
            "strongestDimension": strongest_dimension,
            "densityRatio": round(max_density / min_density, 2) if min_density else 0,
            "zeroChapters": stats["total"]["zeros"],
        },
        "layers": {
            "source": {
                "label": "章节来源",
                "count": len(chapters),
                "detail": "按章节内唯一抽取项统计，保留章节标题和正文长度。",
            },
            "entities": [
                {"key": "characters", "label": "人物实体", "count": metrics["characters"], "chapterTotal": stats["characters"]["sum"]},
                {"key": "locations", "label": "地点实体", "count": metrics["locations"], "chapterTotal": stats["locations"]["sum"]},
                {"key": "events", "label": "事件实体", "count": metrics["events"], "chapterTotal": stats["events"]["sum"]},
            ],
            "network": {
                "label": "关系网络",
                "count": metrics["relations"],
                "chapterTotal": stats["relations"]["sum"],
            },
            "evidence": [
                {"label": "来源章节", "count": len(chapters), "detail": "人物、地点、事件和关系均保留章节标题。"},
                {"label": "地点坐标", "count": metrics["locatedLocations"], "detail": f"{metrics['locatedLocations']}/{metrics['locations']} 个地点已有坐标。"},
                {"label": "事件年份", "count": metrics["timedEvents"], "detail": f"{metrics['timedEvents']}/{metrics['events']} 件事件有数值年份。"},
            ],
        },
    }


REL_KEY_PRIORITY = [
    "父子", "母子", "父女", "母女", "兄弟", "姐妹", "祖孙", "翁婿", "夫妻",
    "君臣", "主臣", "主仆",
    "投奔", "归降", "归顺", "降附", "部将", "部下", "麾下", "水军将领", "献", "效忠",
    "敌对", "征讨", "讨伐", "击败", "大战",
    "盟友", "同盟", "合作", "举荐", "推荐", "师事", "师徒", "同僚", "同乡", "同年", "同门",
]
def key_relation(rels):
    """从同一对节点间的多条关系里挑出最'核心'的一条，用于图谱边标签。"""
    if not rels:
        return ""
    cleaned = [r for r in rels if "同事件" not in r and "推导" not in r]
    pool = cleaned or rels
    for key in REL_KEY_PRIORITY:
        for r in pool:
            if key in r:
                return r
    return pool[0]

def build_visualizations(chars, events, relations, selected_keys, chapter_by_key):
    """Build compact, scope-aware data for the report's visual analysis view."""
    selected_set = set(selected_keys)
    chapters = [
        {
            "key": key,
            "title": chapter_by_key[key]["title"],
            "partKey": key.split("-", 1)[0],
            "part": PARTS.get(key.split("-", 1)[0], chapter_by_key[key]["part"]),
            "order": index,
        }
        for index, key in enumerate(selected_keys)
    ]

    relation_counts = {}
    for relation in relations:
        for name in (relation["from"], relation["to"]):
            relation_counts[name] = relation_counts.get(name, 0) + 1
    event_counts = {}
    for event in events:
        for name in set(event.get("participants", [])):
            event_counts[name] = event_counts.get(name, 0) + 1

    ranked_characters = sorted(
        chars,
        key=lambda item: (
            -len(item.get("chapters", [])),
            -relation_counts.get(item["name"], 0),
            -event_counts.get(item["name"], 0),
            item["name"],
        ),
    )
    heatmap_characters = []
    for character in ranked_characters[:24]:
        chapter_keys = sorted(set(character.get("chapters", [])) & selected_set, key=chapter_key)
        part_counts = {}
        for key in chapter_keys:
            part_key = key.split("-", 1)[0]
            part_counts[part_key] = part_counts.get(part_key, 0) + 1
        heatmap_characters.append({
            "name": character["name"],
            "chapterKeys": chapter_keys,
            "chapterCount": len(chapter_keys),
            "relationCount": relation_counts.get(character["name"], 0),
            "eventCount": event_counts.get(character["name"], 0),
            "partCounts": part_counts,
        })

    type_totals = {}
    for event in events:
        category = event.get("category") or "其他"
        type_totals[category] = type_totals.get(category, 0) + 1
    # 固定类别顺序，按当前范围内数量展示，空类别不出现
    visible_types = [category for category in EVENT_CATEGORIES if type_totals.get(category)]
    primary_types = [category for category in visible_types if category != "其他"]

    part_keys = sorted(
        {key.split("-", 1)[0] for key in selected_keys},
        key=lambda value: int(value[1:]),
    )
    evolution_parts = []
    for part_key in part_keys:
        values = {event_type: 0 for event_type in visible_types}
        for event in events:
            event_parts = {
                source["key"].split("-", 1)[0]
                for source in event.get("sources", [])
                if source["key"] in selected_set
            }
            if part_key not in event_parts:
                continue
            category = event.get("category") or "其他"
            if category in values:
                values[category] += 1
            else:
                values.setdefault("其他", 0)
                values["其他"] += 1
        evolution_parts.append({
            "partKey": part_key,
            "part": PARTS.get(part_key, part_key),
            "values": values,
            "total": sum(values.values()),
        })

    character_names = {character["name"] for character in chars}
    network_names = sorted(
        character_names,
        key=lambda name: (-relation_counts.get(name, 0), -len(next(
            (item for item in chars if item["name"] == name), {"chapters": []}
        ).get("chapters", [])), name),
    )[:80]
    character_lookup = {character["name"]: character for character in chars}
    network_by_name = {}
    for center in network_names:
        grouped = {}
        for relation in relations:
            if relation["from"] != center and relation["to"] != center:
                continue
            outgoing = relation["from"] == center
            other = relation["to"] if outgoing else relation["from"]
            group_key = other
            direction = "out" if outgoing else "in"
            item = grouped.setdefault(group_key, {
                "name": other,
                "directions": [],
                "relations": [],
                "sources": set(),
            })
            if direction not in item["directions"]:
                item["directions"].append(direction)
            if relation["rel"] not in item["relations"]:
                item["relations"].append(relation["rel"])
            item["sources"].add(relation["sourceTitle"])
            item.setdefault("categories", {})
            cat = relation.get("category") or "其他"
            item["categories"][cat] = item["categories"].get(cat, 0) + 1
        neighbors = []
        for item in sorted(
            grouped.values(),
            key=lambda value: (-len(value["sources"]), value["name"]),
        )[:16]:
            other_character = character_lookup.get(item["name"], {})
            dirs = set(item["directions"])
            direction = "both" if len(dirs) > 1 else next(iter(dirs))
            categories = item.get("categories", {})
            dominant = max(categories, key=lambda c: (categories[c], RELATION_CATEGORIES.index(c) if c in RELATION_CATEGORIES else 99), default="其他")
            neighbors.append({
                "name": item["name"],
                "direction": direction,
                "category": dominant,
                "relation": key_relation(item["relations"]),
                "relationCount": len(item["sources"]),
                "chapterCount": len(other_character.get("chapters", [])),
                "sources": sorted(item["sources"])[:5],
            })
        center_character = character_lookup.get(center, {})
        network_by_name[center] = {
            "center": {
                "name": center,
                "chapterCount": len(center_character.get("chapters", [])),
                "relationCount": relation_counts.get(center, 0),
            },
            "neighbors": neighbors,
        }

    return {
        "characterHeatmap": {
            "chapters": chapters,
            "characters": heatmap_characters,
        },
        "eventTypeEvolution": {
            "types": visible_types,
            "primaryTypes": primary_types,
            "parts": evolution_parts,
        },
        "relationNetwork": {
            "names": [
                {
                    "name": name,
                    "relationCount": relation_counts.get(name, 0),
                    "chapterCount": len(character_lookup[name].get("chapters", [])),
                }
                for name in network_names
            ],
            "byName": network_by_name,
        },
    }


def build_relation_graph_full(relations, chars):
    """全书人物关系图数据（只含人物节点；坐标为廉价确定性初始布局）。

    与早期版本的三点不同：
    1. 方案 A：节点只允许人物表 (chars) 内的人物。关系端点里的
       「东林党 / 东厂 / 内阁 / 后金 / 北京 / 明朝 / 黄河」等非人物实体
       一律不进入人物关系图，它们仍保留在关系卡片与详情里（标注端点类型）。
    2. 不再跑 numpy 力导向布局（800 轮 x O(n^2)，实测让构建耗时约 110 秒）。
       这里只给每个节点一个确定性的初始坐标（按势力分扇区 + 扇区内螺旋），
       真正的布局由浏览器端 fullStep() 的实时力模拟完成。
    3. stats.isolated 按「人物表 - 有任何人际关系的人物」计算，
       与页面人物总数、关系图节点数三者自洽。
    """
    char_by_name = {c["name"]: c for c in chars}

    # 1) 只保留两端都是人物表内实体的关系
    person_relations = [r for r in relations
                        if r["from"] in char_by_name and r["to"] in char_by_name]

    # 2) degree / 邻接都在人物集合内统计
    deg = {}
    for r in person_relations:
        deg[r["from"]] = deg.get(r["from"], 0) + 1
        deg[r["to"]] = deg.get(r["to"], 0) + 1
    connected = set(deg.keys())
    isolated = len(char_by_name) - len(connected)
    excluded = len(relations) - len(person_relations)

    if not deg:
        return {"nodes": [], "links": [], "width": 1360.0, "height": 800.0,
                "stats": {"nodes": 0, "edges": 0, "persons": len(char_by_name),
                          "connected": 0, "isolated": isolated,
                          "excludedNonPerson": excluded}}

    nodes = sorted(deg.keys(), key=lambda n: (-deg[n], n))
    n = len(nodes)
    idx = {name: i for i, name in enumerate(nodes)}

    # 3) 去重边（保留主导类别与原始条数）
    edge_groups = {}
    for r in person_relations:
        a, b = r["from"], r["to"]
        if a == b:
            continue
        i, j = idx[a], idx[b]
        key = (i, j) if i < j else (j, i)
        grp = edge_groups.setdefault(key, {"count": 0, "cats": {}})
        grp["count"] += 1
        cat = r.get("category") or "其他"
        grp["cats"][cat] = grp["cats"].get(cat, 0) + 1
    edges = []
    for (i, j), grp in edge_groups.items():
        dominant = max(grp["cats"], key=lambda c: (grp["cats"][c],
                         RELATION_CATEGORIES.index(c) if c in RELATION_CATEGORIES else 99))
        edges.append((i, j, dominant, grp["count"]))

    # 4) 确定性初始布局：势力分扇区，扇区内螺旋（O(n)，无随机、无 numpy）
    def tier_of(name):
        return (char_by_name.get(name, {}).get("faction", "") or "未知").split("·")[0]

    buckets = {}
    for name in nodes:
        buckets.setdefault(tier_of(name), []).append(name)
    ordered_tiers = sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    total = max(n, 1)
    out_nodes = []
    angle_cursor = -math.pi / 2.0
    for tier_name, members in ordered_tiers:
        share = len(members) / total
        span = share * 2.0 * math.pi
        members_sorted = sorted(members, key=lambda nm: (-deg[nm], nm))
        count = max(len(members_sorted), 1)
        for k, name in enumerate(members_sorted):
            t = (k + 0.5) / count
            angle = angle_cursor + span * t
            radius = 240.0 + 26.0 * math.sqrt(k + 1) * (1.0 + 4.0 * share)
            x = 680.0 + radius * math.cos(angle)
            y = 400.0 + radius * 0.62 * math.sin(angle)
            d = deg[name]
            out_nodes.append({
                "name": name,
                "faction": char_by_name[name].get("faction", "") or "未知",
                "tier": tier_name,
                "role": char_by_name[name].get("role", "") or "",
                "degree": d,
                "r": round(min(3 + d ** 0.5 * 1.0, 20), 1),
                "x": round(x, 1),
                "y": round(y, 1),
            })
        angle_cursor += span

    # 归一化到 1280 宽画布，保持比例
    xs = [nd["x"] for nd in out_nodes]
    ys = [nd["y"] for nd in out_nodes]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    pad = 40.0
    scale = 1280.0 / max(maxx - minx, 1.0)
    for nd in out_nodes:
        nd["x"] = round((nd["x"] - minx) * scale + pad, 1)
        nd["y"] = round((nd["y"] - miny) * scale + pad, 1)
    width = 1280.0 + 2 * pad
    height = (maxy - miny) * scale + 2 * pad

    out_links = [{"source": nodes[i], "target": nodes[j], "category": cat, "count": cnt}
                 for (i, j, cat, cnt) in edges]
    return {
        "nodes": out_nodes,
        "links": out_links,
        "width": round(max(width, 1.0), 1),
        "height": round(max(height, 1.0), 1),
        "stats": {
            "nodes": n,
            "edges": len(edges),
            "persons": len(char_by_name),
            "connected": len(connected),
            "isolated": isolated,
            "excludedNonPerson": excluded,
        },
    }



def build_scope(scope: str):
    data = load_json(DATA_PATH, {})
    raw_list = load_json(RAW_PATH, [])
    chapter_records = load_json(CHAPTERS_PATH, [])
    raw_by_key = {item.get("key"): item for item in raw_list}
    all_chapter_keys = sorted(
        (key for key, item in raw_by_key.items() if item.get("type", "chapter") == "chapter"),
        key=chapter_key,
    )
    selected_keys = [key for key in all_chapter_keys if scope == "full" or key.startswith(f"{scope}-")]
    selected_set = set(selected_keys)
    chapter_by_key = {
        key: {
            "title": chapter_title(key, raw_by_key),
            "part": raw_by_key[key].get("part") or raw_by_key[key].get("part_title") or PARTS.get(key[:2], ""),
        }
        for key in selected_keys
    }

    events = []
    for index, event in enumerate(data.get("events", []), 1):
        keys = sorted(set(event.get("chapters", [])) & selected_set, key=chapter_key)
        if not keys:
            continue
        start, end = year_bounds(event.get("year", ""))
        events.append({
            "id": f"event-{index:04d}",
            "type": "event",
            "name": event.get("name", "未命名事件"),
            "year": event.get("year", ""),
            "year_source": event.get("year_source", ""),
            "year_approx": event.get("year_approx", False),
            "year_note": event.get("year_note", ""),
            "year_start": start,
            "year_end": end,
            "type": event.get("type") or "其他",
            "category": event.get("category") or canon_event_type(event.get("type"), event.get("name", "")),
            "location": event.get("location") or "未标注",
            "participants": [canonical(x) for x in event.get("participants", [])],
            "sources": source_items(keys, chapter_by_key),
        })
    events.sort(key=lambda item: (
        item["year_start"] is None,
        item["year_start"] if item["year_start"] is not None else 9999,
        item["year_end"] if item["year_end"] is not None else 9999,
        item["name"],
    ))

    event_by_name = {item["name"]: item for item in events}
    all_event_by_name = {item.get("name"): item for item in data.get("events", [])}

    # 事件引用地点补入 geo 库：把事件中出现、但不在地点库的真实地名合入 raw_locations，
    # 别名挂到已入库地点的 mentioned_as。必须在下面的归一化循环「之前」完成，
    # 这样新增地点才会走同一套字段构造（id/modern/mentionedAs/trace/region/directEvents…），
    # 否则前端 locationCard/locationDetailHTML 会因缺字段而抛 TypeError。
    raw_locations = list(data.get("locations", []))
    _ep_path = os.path.join(BASE, "data", "event_places.json")
    if os.path.exists(_ep_path):
        _ep = json.load(open(_ep_path, encoding="utf-8"))
        _by_ancient = {l.get("ancient"): l for l in raw_locations}
        for _alias, _canon in (_ep.get("aliases") or {}).items():
            _c = _by_ancient.get(_canon)
            if _c is not None:
                _c.setdefault("mentioned_as", [])
                if _alias not in _c["mentioned_as"]:
                    _c["mentioned_as"].append(_alias)
        for _name, _vals in (_ep.get("coords") or {}).items():
            _l = _by_ancient.get(_name)
            if _l is not None:
                if _l.get("lng") is None:
                    _l["lng"], _l["lat"] = _vals[0], _vals[1]
                    _l["modern_address"] = _vals[2]
                    _l["trace_type"] = _vals[3]
                    _l["status"] = "坐标来自内置地名词典（待核验）"
                continue
            _chs = []
            for _e in data.get("events", []):
                _toks = [t.strip() for t in re.split(r"[/、·,，（）()]", _e.get("location") or "")]
                if _name in _toks:
                    for _k in _e.get("chapters", []):
                        if _k not in _chs:
                            _chs.append(_k)
            raw_locations.append({
                "ancient": _name, "mentioned_as": [], "chapters": _chs,
                "lng": _vals[0], "lat": _vals[1], "modern_address": _vals[2],
                "trace_type": _vals[3], "status": "坐标来自内置地名词典（待核验）",
                "note": "事件引用地点，由内置地名词典补坐标（待核验）",
            })

    locations = []
    for location in raw_locations:
        keys = sorted(set(location.get("chapters", [])) & selected_set, key=chapter_key)
        if not keys:
            continue
        ancient = location.get("ancient", "未命名地点")
        direct_events = []
        related_events = []
        aliases = set(location.get("mentioned_as", [])) | {ancient}
        for event in events:
            event_source_keys = {source["key"] for source in event["sources"]}
            if not event_source_keys & set(keys):
                continue
            loc = event.get("location") or ""
            loc_tokens = [t.strip() for t in loc.replace("、", "/").replace("·", "/").replace("，", "/").replace(",", "/").split("/") if t.strip()]
            is_direct = any(t in aliases for t in loc_tokens) or ancient in event.get("name", "")
            nm = event["name"]
            if is_direct:
                if nm not in direct_events:
                    direct_events.append(nm)
            elif nm not in related_events:
                related_events.append(nm)
        related_count = len(related_events)
        related_people = []
        for nm in related_events:
            ev = event_by_name.get(nm) or all_event_by_name.get(nm)
            if ev:
                for p in ev.get("participants", []):
                    if p not in related_people:
                        related_people.append(p)
        related_people = related_people[:20]
        coordinates = location.get("lng") is not None and location.get("lat") is not None
        status = location.get("status") or ("已定位" if coordinates else "待定位")
        locations.append({
            "id": f"location-{len(locations) + 1:04d}",
            "entityId": entity_id("place", ancient),   # Phase 3：跨模块稳定 ID（同地名永远同 ID）
            "type": "place",
            "ancient": ancient,
            "modern": location.get("modern_address") or "地址待考",
            "mentionedAs": location.get("mentioned_as", []),
            "lng": location.get("lng"),
            "lat": location.get("lat"),
            "trace": location.get("trace_type") or "地名",
            "status": status,
            "note": location.get("note") or "",
            "region": region_name(location.get("modern_address", "")),
            "chapters": source_items(keys, chapter_by_key),
            "directEvents": direct_events[:12],
            "relatedEventCount": related_count,
            "relatedEvents": related_events[:20],
            "relatedPeople": related_people,
        })
    locations.sort(key=lambda item: (item["region"], item["ancient"]))

    # 分部范围的人物集合：用于关系范围过滤（P1-11）。
    # 判定条件与下面 chars 的构造完全一致（该人物在本范围内至少有一章），
    # 保证「关系留下的人」与「人物表里的人」是同一个集合。
    scope_names = set()
    for character in data.get("characters", []):
        if set(character.get("chapters", [])) & selected_set:
            scope_names.add(canonical(character.get("name", "未命名人物")))

    # 关系范围策略（必须在 UI 上写明当前用的是哪一种）：
    #   full    → all      ：全书报告保留全部关系
    #   分部报告 → induced ：两端都在本范围内（严格局部图），
    #               避免 p1 里出现 754 条两边人物都不属于 p1 的"串范围"关系。
    relation_scope = "all" if scope == "full" else "induced"

    # Keep every relation in the report data.  The UI paginates it instead of
    # silently truncating it on character cards.
    relations = []
    # 关系端点类型（人物/地点/派系机构/其他）：merge 阶段判定，用于把非人物端点标出来，
    # 避免读者把「东林党」「东厂」「后金」误当成真实人物。
    endpoint_kinds = {}
    for relation in data.get("relations", []):
        source_key = relation.get("chapter", "")
        # 人工增补（curated）与推导（推导）为全局来源，跨范围始终保留；
        # 仅按章节抽取的关系按所选范围过滤。
        if source_key not in selected_set and source_key != "curated" and source_key != "推导":
            continue
        from_name = canonical(relation.get("from", "未命名"))
        to_name = canonical(relation.get("to", "未命名"))
        if relation_scope == "induced" and not (from_name in scope_names and to_name in scope_names):
            continue
        ek = relation.get("endpoint_kind") or {}
        for _side, _raw in (("from", relation.get("from")), ("to", relation.get("to"))):
            _k = ek.get(_side)
            if _raw and _k and _k != "person":
                endpoint_kinds[_raw] = _k
        relations.append({
            "id": relation_id(from_name, to_name, relation.get("rel", "关系待补"), source_key),
            "from": from_name,
            "to": to_name,
            "sourceId": entity_id(ek.get("from") or "person", from_name),
            "targetId": entity_id(ek.get("to") or "person", to_name),
            "sourceType": ek.get("from") or "person",
            "targetType": ek.get("to") or "person",
            "rel": relation.get("rel", "关系待补"),
            "category": relation.get("category") or canon_relation_category(relation.get("rel", "")),
            "endpointKind": {"from": ek.get("from") or "person", "to": ek.get("to") or "person"},
            "source": source_key,
            "sourceTitle": "人工整理" if source_key == "curated" else ("推导（同事件关联）" if source_key == "推导" else chapter_title(source_key, raw_by_key)),
        })
    relations.sort(key=lambda item: (item["from"], item["to"], item["rel"]))

    relation_by_from = {}
    relation_by_to = {}
    for relation in relations:
        relation_by_from.setdefault(relation["from"], []).append(relation)
        relation_by_to.setdefault(relation["to"], []).append(relation)

    chars_by_name = {}
    for character in data.get("characters", []):
        keys = sorted(set(character.get("chapters", [])) & selected_set, key=chapter_key)
        if not keys:
            continue
        name = canonical(character.get("name", "未命名人物"))
        item = chars_by_name.setdefault(name, {
            "name": name, "faction": "", "role": "", "birth": "不详", "life": "不详",
            "aliases": [], "chapters": [], "profiled": False,
        })
        item["faction"] = item["faction"] or character.get("faction", "")
        item["role"] = item["role"] or clean_role(character.get("role", ""))
        item["birth"] = item["birth"] if item["birth"] != "不详" else character.get("birth", "不详")
        item["life"] = item["life"] if item["life"] != "不详" else character.get("life", "不详")
        item["profiled"] = item["profiled"] or bool(character.get("life") or character.get("birth") or character.get("role_clean"))
        item["aliases"] = sorted(set(item["aliases"]) | set(character.get("aliases", [])))
        item["chapters"] = sorted(set(item["chapters"]) | set(keys), key=chapter_key)

    chars = []
    event_participants = {name: [] for name in chars_by_name}
    for event in events:
        for participant in event["participants"]:
            if participant in event_participants:
                event_participants[participant].append(event["name"])
    events_by_chapter = {}
    for event in events:
        for key in event.get("chapters", []):
            events_by_chapter.setdefault(key, []).append(event)
    for character in chars_by_name.values():
        character["aliases"] = sorted(set(character["aliases"] + [name for name, canon_name in CANON.items() if canon_name == character["name"]]))
        character["events"] = sorted(set(event_participants.get(character["name"], [])))
        ctx, seen = [], set()
        for key in character["chapters"]:
            for event in events_by_chapter.get(key, []):
                if character["name"] in event.get("participants", []):
                    continue
                if event["name"] not in seen:
                    seen.add(event["name"])
                    ctx.append(event["name"])
        character["contextEvents"] = ctx
        character["derivedCount"] = len(character.get("chapters_derived", []))
        _is_synthetic = lambda r: ("同事件" in r["rel"]) or ("推导" in r["rel"])
        outgoing = [
            {**relation, "rel": relation["rel"], "dir": "out", "other": relation["to"],
             "otherKind": (relation.get("endpointKind") or {}).get("to")}
            for relation in relation_by_from.get(character["name"], [])
            if not _is_synthetic(relation)
        ]
        incoming = [
            {**relation, "rel": relation["rel"], "dir": "in", "other": relation["from"],
             "otherKind": (relation.get("endpointKind") or {}).get("from")}
            for relation in relation_by_to.get(character["name"], [])
            if relation["from"] != character["name"] and not _is_synthetic(relation)
        ]
        character["relations"] = sorted(
            outgoing + incoming,
            key=lambda relation: (relation["other"], relation["rel"], relation["dir"]),
        )
        character["summary"] = character["role"] if character["role"] != "身份待补" else (character["events"][0] if character["events"] else "书中提及人物")
        character["status"] = "人工精校" if character["profiled"] else "抽取草稿"
        # Phase 3：稳定 ID + 实体类型 + 结构化派系
        character["id"] = entity_id("person", character["name"])
        character["type"] = "person"
        character["factions"] = parse_factions(character.get("faction"), character.get("role"))
        character["factionRaw"] = character.get("faction", "")
        chars.append(character)
    chars.sort(key=lambda item: (-len(item["chapters"]), -len(item["events"]), item["name"]))

    chapter_locations = []
    location_by_name = {item["ancient"]: item for item in locations}
    for key in selected_keys:
        raw_item = raw_by_key[key]
        items = []
        seen = set()
        for place in raw_item.get("locations", []):
            ancient = place.get("ancient", "未命名地点")
            if ancient in seen:
                continue
            seen.add(ancient)
            normalized = location_by_name.get(ancient, {})
            items.append({
                "ancient": ancient,
                "modern": normalized.get("modern", "地址待考"),
                "status": normalized.get("status", "待定位"),
                "directEvents": normalized.get("directEvents", []),
            })
        if items:
            chapter_locations.append({
                "key": key,
                "title": chapter_by_key[key]["title"],
                "part": chapter_by_key[key]["part"],
                "items": items,
            })

    timed_events = [event for event in events if event["year_start"] is not None]
    unknown_events = [event for event in events if event["year_start"] is None]
    located = sum(1 for location in locations if location["lng"] is not None and location["lat"] is not None)
    scope_label = "七部全书" if scope == "full" else PARTS.get(scope, scope)
    metrics = {
        "chapters": len(selected_keys),
        "locations": len(locations),
        "locatedLocations": located,
        "events": len(events),
        "timedEvents": len(timed_events),
        "unknownEvents": len(unknown_events),
        "characters": len(chars),
        "relations": len(relations),
    }
    distribution = build_distribution(
        raw_by_key,
        selected_keys,
        chapter_by_key,
        chapter_records,
        metrics,
    )
    visualizations = build_visualizations(
        chars,
        events,
        relations,
        selected_keys,
        chapter_by_key,
    )
    reign_list = data.get("reigns", [])

    def era_of_year(year):
        for r in reign_list:
            if r["start"] <= year <= r["end"]:
                return r["era"], r["order"]
        if year < 1368:
            return "明兴之前", 0
        return "甲申之后", 99

    era_by_part_map = {}
    for event in events:
        ys = event["year_start"]
        if ys is None:
            continue
        label, order = era_of_year(ys)
        for source in event["sources"]:
            pk = source["key"][:2]
            bucket = era_by_part_map.setdefault(pk, {})
            entry = bucket.setdefault(label, {"count": 0, "order": order})
            entry["count"] += 1
    era_rows = []
    for pk in sorted(era_by_part_map, key=lambda pkey: int(pkey[1:])):
        segs = [{"era": lab, "count": v["count"], "order": v["order"]} for lab, v in era_by_part_map[pk].items()]
        segs.sort(key=lambda seg: seg["order"])
        era_rows.append({
            "partKey": pk,
            "part": PARTS.get(pk, pk),
            "total": sum(seg["count"] for seg in segs),
            "segCount": len(segs),
            "segments": segs,
        })

    # 郑和下西洋：停靠点坐标。优先用 geo 库已有坐标，否则回退到内置示意坐标（明确标注待核验）。
    VOYAGE_COORDS = {
        "南京": (118.78, 32.04, "宝船厂起航，七下西洋的出发地"),
        "占城": (109.22, 12.25, "中南半岛南端（今越南），首站补给"),
        "爪哇": (110.43, -7.10, "满者伯夷所属，南洋枢纽"),
        "三佛齐": (104.75, -2.99, "苏门答腊巨港，旧港宣慰司"),
        "马六甲海峡": (101.50, 2.50, "东西洋航路咽喉"),
        "苏门答腊": (100.55, -0.55, "满剌加之外的苏门答腊西岸"),
        "锡兰山": (79.86, 6.93, "今斯里兰卡，立碑布施"),
        "古里": (75.78, 11.25, "今印度卡利卡特，西洋大港"),
        "溜山": (73.22, 3.20, "今马尔代夫，珊瑚岛国"),
        "红海": (38.50, 22.00, "通往天方（麦加）的门户"),
        "东非": (45.32, 2.05, "麻林等国（今索马里一带），远抵非洲"),
    }
    voyages_meta = data.get("voyages") or {}
    # 停靠点 × 书中事件：直接匹配 = 事件 location 提及该停靠点、且章节落在航线章
    # （航线章 = 「下西洋/西洋」事件所在章，即 p2-c4）；无直接匹配的停靠点
    # 回退列出「本航线核心事件」（下西洋主线 + 各停靠点直接命中的并集）。
    def _ev_ref(_e):
        return {"id": _e["id"], "name": _e["name"], "year": _e["year"]}
    _voyage_chs = set()
    for _e in events:
        if "下西洋" in _e["name"] or "西洋" in (_e["location"] or ""):
            _voyage_chs.update(s["key"] for s in _e["sources"])
    _stop_events = {}
    _core_ids = set()
    for _stop in voyages_meta.get("stops", []):
        _direct = [_e for _e in events
                   if _stop in (_e["location"] or "")
                   and any(s["key"] in _voyage_chs for s in _e["sources"])]
        _stop_events[_stop] = [_ev_ref(_e) for _e in _direct[:6]]
        for _e in _direct:
            _core_ids.add(_e["id"])
    for _e in events:
        if "下西洋" in _e["name"] and any(s["key"] in _voyage_chs for s in _e["sources"]):
            _core_ids.add(_e["id"])
    _core_events = [_ev_ref(_e) for _e in events if _e["id"] in _core_ids][:5]
    voyage_points = []
    for stop in voyages_meta.get("stops", []):
        loc = location_by_name.get(stop)
        if loc and loc.get("lng") is not None and loc.get("lat") is not None:
            _pt = {"name": stop, "lng": loc["lng"], "lat": loc["lat"],
                   "desc": f"书中地点（已定位）：{loc.get('modern_address','')}"}
        elif stop in VOYAGE_COORDS:
            lng, lat, desc = VOYAGE_COORDS[stop]
            _pt = {"name": stop, "lng": lng, "lat": lat, "desc": desc}
        else:
            continue
        _direct = _stop_events.get(stop) or []
        _pt["events"] = _direct if _direct else _core_events
        _pt["eventsDirect"] = bool(_direct)
        voyage_points.append(_pt)
    voyages = {"name": voyages_meta.get("name", ""), "note": voyages_meta.get("note", ""),
               "points": voyage_points, "illustrative": bool(voyage_points and not all(
                   location_by_name.get(s) for s in voyages_meta.get("stops", [])))}

    # 数据清洗面板：补上关系/事件类别计数（meta.cleaning 仅有合并信息，类别计数在此实时统计）
    rel_cat = {}
    for r in relations:
        c = r.get("category") or "其他"
        rel_cat[c] = rel_cat.get(c, 0) + 1
    ev_cat = {}
    for e in events:
        c = e.get("category") or "其他"
        ev_cat[c] = ev_cat.get(c, 0) + 1
    cleaning = dict(data.get("meta", {}).get("cleaning", {}) or {})
    cleaning["relation_categories"] = rel_cat
    cleaning["event_categories"] = ev_cat

    # 全局别名索引：alias → 规范名。
    # 只收"像人名"的别名（2~10 字、不含标点），把抽取噪声（如「张献忠籍贯（陕西）」）挡在外面；
    # 规范名优先——别名与某人物规范名同名时不覆盖那个人的名字。
    _real_names = {c["name"] for c in chars}
    alias_index = {}
    for c in chars:
        for a in c.get("aliases", []):
            a = (a or "").strip()
            if not a or a == c["name"] or a in _real_names:
                continue
            if not (2 <= len(a) <= 10) or re.search(r"[（）()，,、;；:：/·\s]", a):
                continue
            alias_index.setdefault(a, c["name"])

    # 实体 ID 索引：id → 展示名（跨模块 deep link / 反查共用）
    entity_index = {c["id"]: c["name"] for c in chars}
    entity_index.update({l["entityId"]: l["ancient"] for l in locations})
    entity_index.update({e["id"]: e["name"] for e in events})

    return {
        "scope": scope,
        "scopeLabel": scope_label,
        # 模型元信息（Phase 3）：schema 版本 + 实体类型表 + id 索引。
        # 前端不再靠字符串猜字段含义，靠 type / *Id 字段。
        "model": {
            "schemaVersion": 2,
            "entityTypes": list(ENTITY_TYPES),
            "idIndex": entity_index,
        },
        # 关系范围策略：all=全书全部关系；induced=只保留两端都在本范围内的关系。
        # 前端在关系视图里如实标注，避免读者误以为分部图是完整的全局网络。
        "relationScope": relation_scope,
        "chapters": {key: chapter_by_key[key] for key in selected_keys},
        "locations": locations,
        "chapterLocations": chapter_locations,
        "events": events,
        "relations": relations,
        "characters": chars,
        "timeline": timed_events,
        "unknownTimeline": unknown_events,
        "distribution": distribution,
        "visualizations": visualizations,
        "relationGraphFull": build_relation_graph_full(relations, chars),
        # 全局别名索引（alias → 规范名）：搜索/关系/事件等模块共用，
        # 避免各视图各写一套"某个人物还能怎么称呼"的判断。
        "aliasIndex": alias_index,
        "metrics": metrics,
        "cleaning": cleaning,
        "relationCategories": RELATION_CATEGORIES,
        "eventCategories": EVENT_CATEGORIES,
        "reigns": data.get("reigns", []),
        "lifespans": data.get("lifespans", []),
        "voyages": voyages,
        "eraByPart": era_rows,
        "endpointKinds": endpoint_kinds,
        "quotes": {k: v for k, v in load_json(BASE / "data" / "character_quotes.json", {}).items() if k != "_comment"},
    }


WEB_DIR = BASE / "web"
TEMPLATE_PATH = WEB_DIR / "template" / "index.html"
CSS_PATH = WEB_DIR / "css" / "app.css"
JS_PATH = WEB_DIR / "js" / "app.js"


def load_template() -> str:
    """读取 web/ 下的骨架 + 样式 + 脚本，内联回单文件文档。

    Phase 4 之前整份模板是 Python 里的 12.5 万字符字面量，改动要同时动
    HTML/CSS/JS 三种语言，编辑体验差且无法语法检查。现在拆到 web/：
    - web/template/index.html  骨架，含 /*{{INLINE_CSS}}*/ 与 /*{{INLINE_JS}}*/ 两个锚点
    - web/css/app.css          样式
    - web/js/app.js            脚本（首行 const DATA=__DATA__; 由 render() 注入）

    拼接结果与拆分前逐字节等价，可用 .dump/_check_split.py 复核。
    """
    skeleton = TEMPLATE_PATH.read_text(encoding="utf-8")
    css = CSS_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    return skeleton.replace("/*{{INLINE_CSS}}*/", css).replace("/*{{INLINE_JS}}*/", js)


HTML_TEMPLATE = load_template()


def compose_document(payload: dict) -> str:
    """把 payload 注入模板，产出最终单文件 HTML（唯一注入实现）。

    build.py 的 standalone target 直接复用本函数，保证「两条构建路径
    不可能产出不同文件」；``</`` 必须转义，否则数据里出现 ``</script>``
    会提前闭合脚本标签。
    """
    document = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
    document = document.replace("__TITLE__", payload["scopeLabel"])
    document = document.replace("__INSIGHT_DATA__", json.dumps(INSIGHT_PAYLOAD, ensure_ascii=False).replace("</", "<\\/"))
    # Normalize the compact inline template before publishing.
    document = document.replace("pages.join('')}`", "pages.join('')}")
    return document


def render(scope: str, output: Path):
    payload = build_scope(scope)
    document = compose_document(payload)
    output.write_text(document, encoding="utf-8")
    print(f"已生成 {output}")
    print("  " + " · ".join(f"{key} {value}" for key, value in payload["metrics"].items()))


def main():
    parser = argparse.ArgumentParser(description="生成静态知识报告")
    parser.add_argument("--scope", choices=("full", "p1", "p2", "p3", "p4", "p5", "p6", "p7"), default="full")
    args = parser.parse_args()
    OUT_PATH.mkdir(parents=True, exist_ok=True)
    if args.scope == "full":
        # 全书报告（唯一根入口）；壹部不再单独生成，避免与全书包重叠造成冗余
        render("full", OUT_PATH / "index.html")
    else:
        render(args.scope, OUT_PATH / f"report_{args.scope}.html")


if __name__ == "__main__":
    main()
