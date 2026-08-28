# -*- coding: utf-8 -*-
"""Generate the static knowledge report from data/data.json.

The report is deliberately generated from one source so that the full-book and
part-one outputs cannot drift.  It is a static HTML artifact with lazy client
rendering; no build tool or third-party Python package is required.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
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
    if value is None or value == "":
        return None, None
    years = [int(x) for x in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", str(value))]
    if not years:
        return None, None
    return years[0], years[-1]


def canonical(name: str) -> str:
    return CANON.get(name, name)


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
            direction = "主动" if outgoing else "反向"
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
            direction = "与".join(item["directions"])
            categories = item.get("categories", {})
            dominant = max(categories, key=lambda c: (categories[c], RELATION_CATEGORIES.index(c) if c in RELATION_CATEGORIES else 99), default="其他")
            neighbors.append({
                "name": item["name"],
                "direction": direction,
                "category": dominant,
                "relation": "；".join(item["relations"][:3]),
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
    """Force-directed layout of the whole-book character relationship graph.

    Coordinates are precomputed in Python (numpy FR) so the static report
    needs no graph library at runtime. Returns nodes (with x/y), deduped
    links (dominant category + raw count), viewBox bounds and summary stats.
    """
    char_by_name = {c["name"]: c for c in chars}
    deg = {}
    for r in relations:
        deg[r["from"]] = deg.get(r["from"], 0) + 1
        deg[r["to"]] = deg.get(r["to"], 0) + 1
    if not deg:
        return {"nodes": [], "links": [], "width": 0, "height": 0,
                "stats": {"nodes": 0, "edges": 0, "isolated": len(chars)}}
    try:
        import numpy as np
    except Exception:
        # fall back to a deterministic circle layout
        nodes = sorted(deg.keys(), key=lambda n: (-deg[n], n))
        n = len(nodes)
        step = 2 * 3.14159265 / max(n, 1)
        out = [{"name": nm, "faction": char_by_name.get(nm, {}).get("faction", "") or "未知",
                "tier": (char_by_name.get(nm, {}).get("faction", "") or "未知").split("·")[0],
                "role": char_by_name.get(nm, {}).get("role", "") or "",
                "degree": deg[nm], "r": round(min(3 + deg[nm] ** 0.5 * 1.2, 26), 1),
                "x": round(680 + 640 * __import__("math").cos(i * step), 1),
                "y": round(400 + 360 * __import__("math").sin(i * step), 1)}
               for i, nm in enumerate(nodes)]
        return {"nodes": out, "links": [], "width": 1360, "height": 800,
                "stats": {"nodes": n, "edges": 0, "isolated": len(chars) - n}}

    nodes = sorted(deg.keys(), key=lambda n: (-deg[n], n))
    idx = {name: i for i, name in enumerate(nodes)}
    n = len(nodes)

    edge_groups = {}
    for r in relations:
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

    rng = np.random.default_rng(20260826)
    pos = rng.normal(0, 1, (n, 2)).astype(np.float64)
    k = np.sqrt(1.0 / n) * 3.0
    t = 0.2
    gravity = 0.015
    src = np.array([e[0] for e in edges], dtype=np.int64)
    tgt = np.array([e[1] for e in edges], dtype=np.int64)
    for _ in range(800):
        diff = pos[None, :, :] - pos[:, None, :]
        dist2 = (diff ** 2).sum(-1) + 1e-9
        dist = np.sqrt(dist2)
        rep = (k * k / dist)[..., None] * (diff / dist[..., None])
        rep[np.arange(n), np.arange(n), 0] = 0.0
        rep[np.arange(n), np.arange(n), 1] = 0.0
        disp = rep.sum(0)
        d2 = dist2[src, tgt]
        dd = np.sqrt(d2) + 1e-9
        att = (dd / k)[:, None] * (diff[src, tgt] / dd[:, None])
        np.add.at(disp, src, -att)
        np.add.at(disp, tgt, att)
        disp -= gravity * pos
        length = np.sqrt((disp ** 2).sum(1)) + 1e-9
        limit = np.minimum(length, t) / length
        pos += disp * limit[:, None]
        t *= 0.993

    xs = pos[:, 0]; ys = pos[:, 1]
    minx, maxx = float(xs.min()), float(xs.max())
    miny, maxy = float(ys.min()), float(ys.max())
    target_w = 1280.0
    scale = target_w / max((maxx - minx), 1e-6)
    pad = 40.0
    norm_x = (xs - minx) * scale + pad
    norm_y = (ys - miny) * scale + pad
    height = float((maxy - miny) * scale + 2 * pad)
    width = float(target_w + 2 * pad)

    def tier(f):
        return (f or "未知").split("·")[0]

    out_nodes = []
    for i, name in enumerate(nodes):
        c = char_by_name.get(name, {})
        d = deg[name]
        out_nodes.append({
            "name": name,
            "faction": c.get("faction", "") or "未知",
            "tier": tier(c.get("faction", "") or "未知"),
            "role": c.get("role", "") or "",
            "degree": d,
            "r": round(min(3 + d ** 0.5 * 1.0, 20), 1),
            "x": round(float(norm_x[i]), 1),
            "y": round(float(norm_y[i]), 1),
        })
    out_links = [{"source": nodes[i], "target": nodes[j], "category": cat, "count": cnt}
                 for (i, j, cat, cnt) in edges]
    return {
        "nodes": out_nodes,
        "links": out_links,
        "width": round(width, 1),
        "height": round(height, 1),
        "stats": {"nodes": n, "edges": len(edges), "isolated": len(chars) - n},
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
            "name": event.get("name", "未命名事件"),
            "year": event.get("year", ""),
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
    locations = []
    for location in data.get("locations", []):
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

    # Keep every relation in the report data.  The UI paginates it instead of
    # silently truncating it on character cards.
    relations = []
    for relation in data.get("relations", []):
        source_key = relation.get("chapter", "")
        # 人工增补（curated）与推导（推导）为全局来源，跨范围始终保留；
        # 仅按章节抽取的关系按所选范围过滤。
        if source_key not in selected_set and source_key != "curated" and source_key != "推导":
            continue
        relations.append({
            "from": canonical(relation.get("from", "未命名")),
            "to": canonical(relation.get("to", "未命名")),
            "rel": relation.get("rel", "关系待补"),
            "category": relation.get("category") or canon_relation_category(relation.get("rel", "")),
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
        outgoing = [
            {**relation, "rel": f"主动·{relation['rel']}", "direction": "outgoing"}
            for relation in relation_by_from.get(character["name"], [])
        ]
        incoming = [
            {**relation, "to": relation["from"], "rel": f"反向·{relation['rel']}", "direction": "incoming"}
            for relation in relation_by_to.get(character["name"], [])
            if relation["from"] != character["name"]
        ]
        character["relations"] = sorted(
            outgoing + incoming,
            key=lambda relation: (relation["to"], relation["rel"], relation["direction"]),
        )
        character["summary"] = character["role"] if character["role"] != "身份待补" else (character["events"][0] if character["events"] else "书中提及人物")
        character["status"] = "人工精校" if character["profiled"] else "抽取草稿"
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

    voyages_meta = data.get("voyages") or {}
    voyage_points = []
    for stop in voyages_meta.get("stops", []):
        loc = location_by_name.get(stop)
        if loc and loc["lng"] is not None and loc["lat"] is not None:
            voyage_points.append({"name": stop, "lng": loc["lng"], "lat": loc["lat"]})
    voyages = {"name": voyages_meta.get("name", ""), "note": voyages_meta.get("note", ""), "points": voyage_points}

    return {
        "scope": scope,
        "scopeLabel": scope_label,
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
        "metrics": metrics,
        "cleaning": data.get("meta", {}).get("cleaning", {}),
        "relationCategories": RELATION_CATEGORIES,
        "eventCategories": EVENT_CATEGORIES,
        "reigns": data.get("reigns", []),
        "lifespans": data.get("lifespans", []),
        "voyages": voyages,
        "eraByPart": era_rows,
    }


HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>明朝那些事儿 · __TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--ink:#27231f;--muted:#716960;--paper:#fffdf8;--wash:#f2eee6;--line:#ded6c9;--accent:#8d3025;--gold:#b88b35;--green:#527b5c;--blue:#476b86;--shadow:0 8px 24px rgba(42,31,21,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--wash);color:var(--ink);font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;font-size:14px;line-height:1.6}button,input,select{font:inherit}button{cursor:pointer}.app-header{position:sticky;top:0;z-index:20;background:#29241f;color:#f7efe2;border-bottom:1px solid #483b31}.header-inner{max-width:1320px;margin:auto;padding:14px 24px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}.brand{margin:0;font-size:21px;line-height:1.2;letter-spacing:.02em}.header-stat{color:#d8cabc;font-size:12px;white-space:nowrap}.tabs{display:flex;gap:6px;margin-left:auto;overflow-x:auto;max-width:100%;padding-bottom:2px}.tabs button,.subnav button{border:1px solid transparent;border-radius:6px;background:#3d352e;color:#eadfd2;padding:7px 12px;white-space:nowrap}.tabs button:hover,.subnav button:hover{border-color:#c5a05f}.tabs button.active,.subnav button.active{background:var(--accent);color:#fff;border-color:var(--accent)}.shell{max-width:1320px;margin:auto;padding:24px 24px 72px}.view{display:none}.view.active{display:block}.section-head{display:flex;align-items:end;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:16px}.section-head h2{margin:0;font-size:24px;color:#3a3029}.section-head p{margin:3px 0 0;color:var(--muted);font-size:13px}.panel{background:var(--paper);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow);padding:18px}.summary-hero{display:grid;grid-template-columns:1.35fr 1fr;gap:18px;margin-bottom:18px}.hero-copy{background:#342c25;color:#f7efe2;border-radius:10px;padding:28px}.hero-copy h2{font-size:28px;margin:0 0 10px;color:#fff}.hero-copy p{margin:0;color:#dfd0c1;max-width:58ch}.hero-note{margin-top:18px;color:#d8bf86;font-size:12px}.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.metric{background:#fff;border:1px solid var(--line);border-radius:8px;padding:15px}.metric .value{display:block;font-size:25px;font-weight:800;color:var(--accent);line-height:1.1}.metric .label{display:block;color:var(--muted);font-size:12px;margin-top:5px}.quality-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.quality-grid .quality{border-left:3px solid var(--gold);background:#fbf8f1;padding:12px 14px}.quality strong{display:block}.quality span{color:var(--muted);font-size:12px}.toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px}.toolbar label{color:var(--muted);font-size:12px}.toolbar input,.toolbar select{min-width:140px;background:#fff;border:1px solid #cfc5b7;border-radius:6px;padding:7px 9px;color:var(--ink)}.toolbar input.search{min-width:220px}.toolbar .grow{flex:1}.subnav{display:flex;gap:7px;margin-bottom:14px}.subnav button{background:#fff;color:var(--muted);border-color:var(--line);padding:6px 11px}.data-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.location-card,.character-card{background:#fff;border:1px solid var(--line);border-radius:9px;box-shadow:0 2px 9px rgba(50,40,30,.05);overflow:hidden}.location-card{padding:16px}.card-head{display:flex;align-items:start;justify-content:space-between;gap:8px}.card-title{font-size:18px;color:var(--accent);font-weight:800}.tag{display:inline-block;background:#f2ead9;color:#775f2e;border-radius:4px;padding:2px 7px;font-size:11px;white-space:nowrap}.status{display:inline-block;border-radius:999px;padding:2px 7px;font-size:11px;background:#edf4ec;color:var(--green)}.status.draft{background:#f6efe4;color:#86632a}.muted{color:var(--muted)}.meta{margin-top:7px;font-size:12px;color:#615851}.meta b{color:#443b34}.event-list{margin:8px 0 0;padding-left:18px;color:#733025;font-size:12px}.event-list li{margin:2px 0}.source-row{display:flex;gap:5px;flex-wrap:wrap;margin-top:9px}.source-chip{display:inline-block;border:1px solid #e1d5c4;color:#6a6058;border-radius:4px;padding:1px 5px;font-size:11px;background:#fffdf8}.source-chip button{border:0;background:none;padding:0;color:inherit}.pagination{display:flex;align-items:center;justify-content:center;gap:9px;margin-top:18px}.pagination button,.action{border:1px solid #cbbda8;background:#fff;border-radius:6px;padding:6px 10px;color:#5f5145}.pagination button:disabled{opacity:.45;cursor:not-allowed}.page-label{color:var(--muted);font-size:12px}.chapter-list{display:grid;gap:12px}.chapter-block{background:#fff;border:1px solid var(--line);border-radius:8px;padding:14px}.chapter-block h3{margin:0 0 7px;color:var(--accent);font-size:16px}.chapter-place{display:grid;grid-template-columns:130px 1fr;gap:8px;border-top:1px dashed #e8dfd3;padding:7px 0;font-size:13px}.chapter-place:first-of-type{border-top:0}.chapter-place strong{color:#3b4651}.map-wrap{position:relative}.map-note{margin-top:8px;color:var(--muted);font-size:12px}.map-box{height:590px;border:1px solid #c9d2d8;border-radius:9px;overflow:hidden;background:#e9eef0}.fallback-map{height:100%;width:100%;display:block;background:#e8efe8}.fallback-map text{font-size:11px;fill:#3e5144}.character-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px}.character-toolbar .mode{border:1px solid #cdbfae;background:#fff;border-radius:6px;padding:6px 10px;color:#5b5047}.character-toolbar .mode.active{background:var(--gold);border-color:var(--gold);color:#2e271f}.character-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px}.character-card{height:255px;perspective:900px;position:relative}.character-card .inner{height:100%;transition:transform .45s;transform-style:preserve-3d}.character-card.flip .inner{transform:rotateY(180deg)}.character-card .face{position:absolute;inset:0;backface-visibility:hidden;padding:16px;display:flex;flex-direction:column}.character-card .front{background:linear-gradient(145deg,#7e2b22,#a54130);color:#fff5ec;align-items:center;justify-content:center;text-align:center}.character-card .front h3{font-size:20px;margin:0}.character-card .front .summary{font-size:12px;color:#f2dcd0;margin-top:10px}.character-card .back{background:#fff;transform:rotateY(180deg);overflow:auto}.character-card .back h3{color:var(--accent);margin:0 0 5px}.card-actions{display:flex;gap:6px;margin-top:auto}.card-actions button{border:1px solid #e3d9ce;background:#fbf7f0;border-radius:5px;padding:4px 8px;color:#6e4b3d;font-size:12px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff}.data-table{width:100%;border-collapse:collapse;min-width:760px}.data-table th,.data-table td{text-align:left;border-bottom:1px solid #eee7de;padding:10px 12px;vertical-align:top}.data-table th{background:#f7f2e9;color:#64584e;font-size:12px;position:sticky;top:0}.data-table td{font-size:13px}.data-table tr:hover{background:#fffaf1}.cat-tag{display:inline-block;border:1px solid color-mix(in srgb,var(--cat) 55%,transparent);background:color-mix(in srgb,var(--cat) 12%,#fff);color:color-mix(in srgb,var(--cat) 82%,#000);border-radius:4px;padding:1px 7px;font-size:11px;white-space:nowrap}.cat-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:-1px;background:var(--cat)}.clean-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.clean-card{border:1px solid var(--line);border-left:3px solid var(--green);background:#fbfaf5;border-radius:8px;padding:12px 14px}.clean-card strong{display:block;font-size:13px;color:#40362f}.clean-card span{color:var(--muted);font-size:12px}.clean-chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}.cat-dist{display:flex;height:12px;border-radius:3px;overflow:hidden;background:#eee8df;margin-top:7px}.cat-dist span{height:100%}.cat-legend{display:flex;flex-wrap:wrap;gap:9px;margin-top:8px;color:var(--muted);font-size:11px}.cat-legend span{display:inline-flex;align-items:center}.link-button{border:0;background:none;padding:0;text-align:left;color:var(--accent);font-weight:700}.timeline{border-left:3px solid var(--gold);padding-left:20px}.year-group{margin:0 0 20px}.year-group h3{margin:0 0 5px;color:var(--accent);font-size:17px}.timeline-item{padding:5px 0;font-size:13px}.timeline-item button{border:0;background:none;color:var(--ink);padding:0;text-align:left}.timeline-item button:hover{color:var(--accent)}.unknown{margin-top:22px;border-top:1px dashed var(--line);padding-top:16px}.empty{padding:36px;text-align:center;color:var(--muted)}dialog{border:0;border-radius:10px;padding:0;width:min(680px,calc(100vw - 32px));box-shadow:0 18px 70px rgba(0,0,0,.28);color:var(--ink)}dialog::backdrop{background:rgba(25,20,15,.5)}.dialog-body{padding:22px}.dialog-head{display:flex;justify-content:space-between;gap:12px;align-items:start;border-bottom:1px solid var(--line);padding-bottom:12px}.dialog-head h2{margin:0;color:var(--accent);font-size:21px}.dialog-close{border:0;background:#f1ebe2;border-radius:5px;padding:4px 9px}.detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:14px}.detail-block{background:#fbf8f2;padding:10px;border-radius:6px}.detail-block strong{display:block;color:#665a4f;font-size:11px;margin-bottom:3px}.detail-block p{margin:0}.detail-wide{grid-column:1/-1}.print-area{display:none}.print-page{width:210mm;min-height:297mm;margin:0 auto 12px;padding:8mm;background:#fff;position:relative}.print-grid{display:grid;grid-template-columns:repeat(3,63mm);grid-template-rows:repeat(3,88mm);justify-content:center}.print-card{width:63mm;height:88mm;border:1px dashed #b9a98a;padding:5mm 4mm;overflow:hidden}.print-card.front{background:#8d3025;color:#fff5ec;text-align:center;padding-top:18mm}.print-card .name{font-size:21px;font-weight:800}.print-card .text{font-size:10px;line-height:1.5;margin-top:8mm}.print-card.back{font-size:9px;line-height:1.45}.print-card.back .name{font-size:12px;color:var(--accent);border-bottom:1px solid var(--line);padding-bottom:2px;margin-bottom:4px}.print-guide{background:#fbf5e8;border:1px dashed #c9a24b;padding:10px;border-radius:6px;margin-bottom:13px;color:#6a5630;font-size:12px}.print-actions{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}@media(max-width:1000px){.data-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.character-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.summary-hero{grid-template-columns:1fr}.quality-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.header-inner{padding:13px 16px;gap:10px}.brand{font-size:18px}.header-stat{width:100%}.tabs{width:100%;margin-left:0}.tabs button{flex:1;padding:7px 8px;font-size:12px}.shell{padding:17px 14px 52px}.section-head h2{font-size:21px}.panel{padding:13px}.hero-copy{padding:20px}.hero-copy h2{font-size:23px}.metric-grid,.quality-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.data-grid,.character-grid{grid-template-columns:1fr}.toolbar input.search,.toolbar input{min-width:0;width:100%}.toolbar label{width:auto}.chapter-place{grid-template-columns:92px 1fr}.map-box{height:470px}.character-card{height:245px}.detail-grid{grid-template-columns:1fr}.detail-wide{grid-column:auto}.print-page{width:210mm}.print-area{overflow:auto}}@media print{body{background:#fff}.app-header,.shell>*:not(#characters){display:none!important}#characters{display:block!important}.character-toolbar,.panel,.print-guide{display:none!important}.print-area{display:block!important}.print-page{box-shadow:none;margin:0;page-break-after:always}@page{size:A4;margin:0}}
 .quality-grid .quality{border-left:3px solid var(--gold);background:#fbf8f1;padding:12px 14px}
.distribution-intro{display:grid;grid-template-columns:1.15fr .85fr;gap:14px;margin-bottom:14px}.distribution-callout{background:#342c25;color:#f7efe2;border-radius:9px;padding:20px}.distribution-callout h3{margin:6px 0 7px;font-size:20px;line-height:1.35;color:#fff}.distribution-callout p{margin:0;color:#dfd0c1;font-size:12px}.signal{display:inline-block;color:#f0d18c;font-size:11px;letter-spacing:.08em}.distribution-stat-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.distribution-stat{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px}.distribution-stat strong{display:block;color:var(--accent);font-size:20px;line-height:1.2}.distribution-stat span{display:block;margin-top:4px;color:var(--muted);font-size:11px}.distribution-legend{display:flex;gap:13px;flex-wrap:wrap;margin:3px 0 14px;color:var(--muted);font-size:12px}.distribution-legend span{display:inline-flex;align-items:center;gap:5px}.legend-dot{width:10px;height:10px;border-radius:2px;display:inline-block}.legend-character{background:#8d3025}.legend-location{background:#b88b35}.legend-event{background:#476b86}.legend-relation{background:#527b5c}.distribution-scale{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:11px;margin-bottom:6px}.part-list{display:grid;gap:11px}.part-row{display:grid;grid-template-columns:minmax(155px,1fr) minmax(240px,2.4fr) 66px 82px;gap:10px;align-items:center}.part-label strong{display:block;color:#40362f;font-size:13px}.part-label span{display:block;color:var(--muted);font-size:11px}.part-bar,.chapter-track,.density-track{height:16px;background:#eee8df;border-radius:3px;overflow:hidden}.part-bar{display:flex;min-width:2px}.part-segment,.chapter-segment{height:100%;display:block}.part-values{text-align:right;font-weight:800;color:var(--accent);font-size:13px}.part-density{text-align:right;color:var(--muted);font-size:11px}.distribution-note{color:var(--muted);font-size:12px;margin:-5px 0 12px}.chapter-header,.chapter-row{display:grid;grid-template-columns:minmax(145px,1.15fr) minmax(210px,2fr) 100px 80px;gap:10px;align-items:center}.chapter-header{color:#756a60;font-size:11px;padding:0 0 6px;border-bottom:1px solid var(--line)}.chapter-list-dist{display:grid;gap:7px}.chapter-row{padding:4px 0;border-bottom:1px solid #eee8df}.chapter-row:last-child{border-bottom:0}.chapter-name{min-width:0}.chapter-name strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#42382f;font-size:12px}.chapter-name span{display:block;color:var(--muted);font-size:10px}.chapter-bars{display:grid;gap:3px}.chapter-track{display:flex;height:12px}.density-track{height:4px;background:#e7edf0}.density-track span{display:block;height:100%;background:var(--blue);border-radius:2px}.chapter-value{text-align:right;font-weight:800;color:var(--accent);font-size:12px}.chapter-density{text-align:right;color:var(--blue);font-size:11px}.layer-flow{display:grid;grid-template-columns:minmax(0,1fr) 28px minmax(0,1.3fr) 28px minmax(0,1fr) 28px minmax(0,1.2fr);gap:8px;align-items:stretch}.layer-node{background:#fbf8f1;border:1px solid var(--line);border-top:3px solid var(--gold);border-radius:7px;padding:13px;min-width:0}.layer-node:nth-child(3){border-top-color:var(--accent)}.layer-node:nth-child(5){border-top-color:var(--green)}.layer-node:nth-child(7){border-top-color:var(--blue)}.layer-node small{display:block;color:var(--muted);font-size:10px;letter-spacing:.08em}.layer-node strong{display:block;margin:3px 0;color:#40362f}.layer-node b{display:block;color:var(--accent);font-size:20px;line-height:1.2}.layer-node span{display:block;margin-top:5px;color:var(--muted);font-size:11px}.layer-connector{display:flex;align-items:center;justify-content:center;color:var(--gold);font-size:21px}.layer-list{margin:7px 0 0;padding-left:16px;color:var(--muted);font-size:11px}.distribution-foot{margin-top:12px;color:var(--muted);font-size:11px;border-top:1px dashed var(--line);padding-top:10px}@media(max-width:1000px){.distribution-intro{grid-template-columns:1fr}.part-row{grid-template-columns:minmax(145px,1fr) minmax(180px,2fr) 62px 76px}.layer-flow{grid-template-columns:1fr 22px 1fr 22px 1fr 22px 1fr}.layer-node{padding:10px}}@media(max-width:640px){.distribution-stat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.distribution-stat{padding:10px}.distribution-stat strong{font-size:17px}.part-row{grid-template-columns:1fr 58px 70px;gap:7px}.part-row .part-bar{grid-column:1/-1;grid-row:2}.part-values{grid-column:2;grid-row:1}.part-density{grid-column:3;grid-row:1}.chapter-header{display:none}.chapter-row{grid-template-columns:minmax(100px,1fr) minmax(110px,1.2fr) 52px 62px;gap:6px}.chapter-name strong{font-size:11px}.chapter-name span{font-size:9px}.chapter-value,.chapter-density{font-size:10px}.layer-flow{grid-template-columns:1fr;gap:6px}.layer-connector{height:18px;transform:rotate(90deg)}.layer-node b{font-size:18px}}
 @media(max-width:640px){.chapter-row{grid-template-columns:minmax(80px,1fr) minmax(80px,1.2fr) 48px 56px}}
 .layer-connector{font-size:0!important;height:1px;background:var(--gold);opacity:.7}
 @media(max-width:640px){.layer-connector{width:1px;height:18px;transform:none}}
 .visuals-stack{display:grid;gap:18px}.visuals-panel{min-width:0}.visuals-panel .section-head{margin-bottom:12px}.visuals-panel h3{margin:0;color:#40362f;font-size:18px}.visuals-panel .section-head p{max-width:72ch}.visual-toolbar{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:0 0 13px}.visual-toolbar label{color:var(--muted);font-size:12px}.visual-toolbar select{min-width:180px;background:#fff;border:1px solid #cfc5b7;border-radius:6px;padding:7px 9px;color:var(--ink)}.visual-note{color:var(--muted);font-size:12px}.heatmap-wrap{overflow-x:auto;overflow-y:hidden;border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px}.heatmap-grid{display:grid;grid-template-columns:190px repeat(var(--heatmap-columns),18px);min-width:max-content;align-items:center;row-gap:4px}.heatmap-corner{height:46px;display:flex;align-items:end;padding:0 8px 5px;color:var(--muted);font-size:11px;position:sticky;left:0;background:#fff;z-index:2}.heatmap-chapter{height:46px;display:flex;align-items:end;justify-content:center;color:#766c63;font-size:10px;writing-mode:vertical-rl;transform:rotate(180deg);padding-bottom:4px}.heatmap-name{height:22px;display:flex;align-items:center;gap:6px;padding:0 8px;position:sticky;left:0;background:#fff;z-index:1;border-top:1px solid #f0ebe4;color:#443a32;font-size:12px;white-space:nowrap}.heatmap-name small{color:var(--muted);font-size:10px}.heatmap-cell{width:14px;height:16px;padding:0;border:0;border-radius:2px;background:#eee8df;box-shadow:none}.heatmap-cell:hover,.heatmap-cell:focus-visible{outline:2px solid var(--accent);outline-offset:1px}.heatmap-cell.present{background:var(--accent)}.heatmap-cell.part-p2.present{background:#b88b35}.heatmap-cell.part-p3.present{background:#476b86}.heatmap-cell.part-p4.present{background:#527b5c}.heatmap-cell.part-p5.present{background:#8d5f42}.heatmap-cell.part-p6.present{background:#6d688c}.heatmap-cell.part-p7.present{background:#a24b55}.heatmap-legend{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:10px;color:var(--muted);font-size:11px}.heatmap-key{width:12px;height:12px;border-radius:2px;display:inline-block;margin-right:4px;vertical-align:-2px}.heatmap-key.present{background:var(--accent)}.heatmap-key.empty{background:#eee8df}.event-legend{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 13px;color:var(--muted);font-size:11px}.event-legend-item{display:inline-flex;align-items:center;gap:5px}.event-legend-item i{display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--event-color,#8d3025)}.evolution-list{display:grid;gap:10px}.evolution-row{display:grid;grid-template-columns:178px minmax(0,1fr) 48px;gap:10px;align-items:center}.evolution-label{min-width:0}.evolution-label strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#443a32;font-size:12px}.evolution-label span{display:block;color:var(--muted);font-size:10px}.evolution-track{height:22px;background:#eee8df;border-radius:3px;overflow:hidden}.evolution-fill{height:100%;display:flex;min-width:2px}.evolution-segment{height:100%;display:block;min-width:1px}.evolution-total{text-align:right;color:var(--accent);font-size:12px;font-weight:800}.network-controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}.network-controls label{color:var(--muted);font-size:12px}.network-controls select{flex:1;min-width:220px;max-width:500px;background:#fff;border:1px solid #cfc5b7;border-radius:6px;padding:7px 9px;color:var(--ink)}.network-summary{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-bottom:5px}.network-summary strong{color:var(--accent)}.network-svg{display:block;width:100%;height:auto;min-height:300px;border:1px solid var(--line);border-radius:8px;background:#fffdf9}.network-svg text{font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif}.network-link{stroke:#c9bda9;stroke-width:1.5}.network-link.incoming{stroke-dasharray:5 4}.network-node{fill:#fff9ef;stroke:#b88b35;stroke-width:1.5}.network-node.center{fill:#8d3025;stroke:#8d3025}.network-label{fill:#443a32;font-size:12px;text-anchor:middle}.network-label.center{fill:#fff9ef;font-weight:700}.network-edge-label{fill:#766c63;font-size:9px;text-anchor:middle}.network-empty{padding:28px;text-align:center;color:var(--muted)}@media(max-width:1000px){.evolution-row{grid-template-columns:150px minmax(0,1fr) 44px}.heatmap-grid{grid-template-columns:170px repeat(var(--heatmap-columns),18px)}}@media(max-width:640px){.visuals-panel{padding:13px}.visuals-panel h3{font-size:17px}.heatmap-grid{grid-template-columns:135px repeat(var(--heatmap-columns),18px)}.heatmap-corner{height:40px}.heatmap-chapter{height:40px}.heatmap-name{font-size:11px}.heatmap-name small{display:none}.evolution-row{grid-template-columns:1fr 52px;gap:6px}.evolution-label{grid-column:1/-1}.evolution-track{grid-column:1}.evolution-total{grid-column:2;grid-row:2}.network-controls select{width:100%;min-width:0;max-width:none}.network-svg{min-height:0}.network-edge-label{font-size:8px}.network-label{font-size:11px}}

.era-tag{display:inline-block;margin-left:8px;padding:1px 8px;border-radius:999px;background:#f2ead9;color:#775f2e;font-size:11px;font-weight:400;vertical-align:2px}
.dynasty-band{display:flex;gap:2px;height:52px;align-items:stretch;margin-bottom:10px}
.dynasty-seg{min-width:4px;border-radius:4px;color:#fff;font-size:11px;display:flex;align-items:flex-end;justify-content:center;padding:3px 2px;cursor:pointer;overflow:hidden;white-space:nowrap}
.dynasty-seg:hover{filter:brightness(1.12)}
.dynasty-hist{display:flex;gap:1px;align-items:flex-end;height:84px;background:#faf6ee;border-radius:6px;padding:4px}
.dynasty-hist span{flex:1;min-width:1px;border-radius:1px 1px 0 0}
.dynasty-scale{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin-top:6px}
.dynasty-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.dynasty-card{background:#fff;border:1px solid var(--line);border-top:4px solid var(--cat);border-radius:9px;padding:14px;cursor:pointer;box-shadow:0 2px 9px rgba(50,40,30,.05);transition:transform .15s ease}
.dynasty-card:hover{transform:translateY(-2px)}
.dynasty-card.active{outline:2px solid var(--cat);outline-offset:1px}
.dynasty-card h3{margin:0;font-size:20px;color:var(--cat)}
.dynasty-card .muted{font-size:12px;margin-top:3px}
.dynasty-card p{font-size:12px;margin:8px 0 0;color:#615851;line-height:1.55}
.dynasty-detail-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:16px}
.dynasty-event-row{display:flex;justify-content:space-between;gap:10px;align-items:baseline;border-bottom:1px dashed #eee7de;padding:7px 2px;font-size:13px}
@media(max-width:1000px){.dynasty-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.dynasty-detail-grid{grid-template-columns:1fr}}
@media(max-width:640px){.dynasty-cards{grid-template-columns:1fr}.dynasty-band{height:40px}}
.chronicle-wrap{position:relative;overflow:hidden}.chronicle-band{position:absolute;top:0;bottom:0;opacity:.16;z-index:0}.chronicle-content{position:relative;z-index:1}.chronicle-axis{position:relative;height:20px;border-bottom:1px solid var(--line);margin-bottom:8px}.chronicle-tick{position:absolute;transform:translateX(-50%);font-size:10px;color:var(--muted)}.chronicle-group{margin:15px 0 5px;font-size:13px;font-weight:700;color:#40362f;display:flex;align-items:center}.chronicle-row{display:grid;grid-template-columns:132px 1fr;gap:10px;align-items:center;padding:2px 0}.chronicle-name{text-align:right;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.chronicle-track{position:relative;height:14px;background:#f3eee4;border-radius:3px}.chronicle-bar{position:absolute;top:3px;height:8px;border-radius:2px}.voyage-num{background:none;border:none;color:#8a6a1f;font-weight:700;font-size:11px;text-shadow:0 1px 0 #fff}@media(max-width:640px){.chronicle-row{grid-template-columns:92px 1fr}}
.map-layout{display:flex;gap:14px;align-items:stretch}
.map-main{flex:1;min-width:0}
.loc-dock{flex:0 0 336px;width:336px;max-height:590px;overflow:auto;background:var(--paper);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow);padding:14px 16px}
.loc-dock[hidden]{display:none}
.loc-dock .dock-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:10px}
.loc-dock .dock-head h3{margin:0;color:var(--accent);font-size:19px;line-height:1.3}
.loc-dock .dock-close{border:0;background:#f1ebe2;border-radius:5px;padding:4px 9px;white-space:nowrap}
.loc-dock .detail-grid{margin-top:0}
@media(max-width:760px){.map-layout{flex-direction:column}.map-main{order:1}.loc-dock{flex:none;width:auto;max-height:340px;order:2}
#fullNet{position:relative}.full-graph-canvas{display:block;width:100%;height:auto;min-height:320px;cursor:grab;background:#fffdf9;border:1px solid var(--line);border-radius:8px}.full-graph-canvas.dragging{cursor:grabbing}.full-graph-tip-box{position:fixed;pointer-events:none;background:rgba(40,33,28,.92);color:#fffdf9;font-size:12px;padding:5px 8px;border-radius:6px;max-width:240px;white-space:nowrap;transform:translate(-50%,calc(-100% - 12px));display:none;z-index:50}.full-graph-tip{color:var(--muted);font-size:12px}
/* 详情弹窗：移动端与长内容下保证可滚动、不溢出视口 */
#detailDialog{max-width:min(900px,94vw);max-height:90vh;padding:0;border:0}
.dialog-body{max-height:90vh;overflow:auto}
/* 窄屏：总览与分布的双栏布局折叠为单列，收紧内边距 */
@media(max-width:760px){.summary-hero{grid-template-columns:1fr}.distribution-intro{grid-template-columns:1fr}.panel{padding:14px}.hero-copy{padding:20px}.metric-grid{gap:8px}.section-head h2{font-size:20px}}
/* 力导图悬浮提示：允许换行，避免超长文本溢出 */
.full-graph-tip-box{white-space:normal}
.src-tag{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:10px;background:#e9ddc6;color:#8a6a2a;font-size:11px;vertical-align:middle}
.src-note{display:inline-block;margin-left:4px;color:var(--muted);font-size:12px}</style>
</head>
<body>
<header class="app-header"><div class="header-inner">
  <h1 class="brand">明朝那些事儿 · __TITLE__</h1><div id="headerStat" class="header-stat"></div>
  <nav class="tabs" aria-label="报告视图">
    <button data-view="overview" class="active">总览</button><button data-view="distribution">分布</button><button data-view="visuals">图谱</button><button data-view="locations">地点</button><button data-view="map">地图</button><button data-view="characters">人物</button><button data-view="events">事件</button><button data-view="relations">关系</button><button data-view="timeline">时间轴</button><button data-view="dynasty">帝王</button><button data-view="chronicle">年谱</button>
  </nav>
</div></header>
<main class="shell">
  <section id="overview" class="view active"></section>
  <section id="distribution" class="view"></section>
  <section id="visuals" class="view"></section>
  <section id="locations" class="view"></section>
  <section id="map" class="view"><div class="section-head"><div><h2>地图</h2><p>仅显示已有坐标的地点；点位与地址均保留核验状态。点击任一红点，右侧面板会显示该地点的书中介绍，可随时切换节点。</p></div></div><div class="panel map-wrap"><div class="toolbar" id="voyageToolbar" style="margin-bottom:10px"><span id="voyageToggleWrap"><label style="display:inline-flex;gap:6px;align-items:center;color:var(--ink)"><input type="checkbox" id="voyageToggle">郑和下西洋（示意航线）</label></span><span class="muted grow" id="voyageNote"></span></div><div class="map-layout"><div class="map-main"><div id="mapBox" class="map-box"></div><div class="map-note" id="mapNote"></div></div><aside id="locDock" class="loc-dock" hidden></aside></div></div></section>
  <section id="characters" class="view"></section>
  <section id="events" class="view"></section>
  <section id="relations" class="view"></section>
  <section id="timeline" class="view"></section>
  <section id="dynasty" class="view"></section>
  <section id="chronicle" class="view"></section>
</main>
<dialog id="detailDialog"><div class="dialog-body"><div class="dialog-head"><h2 id="dialogTitle"></h2><button class="dialog-close" id="dialogClose">关闭</button></div><div id="dialogContent"></div></div></dialog>
<footer class="muted" style="text-align:center;padding:0 24px 28px;font-size:12px">数据来自章节抽取与人工整理；地点、年份及关系均保留核验状态。</footer>
<script>
const DATA=__DATA__;
const PARTS={p1:'壹部 · 洪武大帝',p2:'贰部 · 万国来朝',p3:'叁部 · 妖孽宫廷',p4:'肆部 · 粉饰太平',p5:'伍部 · 帝国飘摇',p6:'陆部 · 日暮西山',p7:'柒部 · 大结局'};
const REL_CAT_COLORS={'亲属':'#8d3025','君臣从属':'#b88b35','师生同门':'#706b91','同盟友党':'#527b5c','敌对冲突':'#a24b55','政治攻讦':'#476b86','婚姻姻亲':'#c06a8a','地点关联':'#8c6344','其他':'#9d9a8d'};
const EVENT_CAT_COLORS={'军事战争':'#8d3025','政治斗争':'#476b86','案件刑狱':'#706b91','人事任免':'#b88b35','制度科举':'#527b5c','外交边务':'#8c6344','宫廷变故':'#a24b55','民变起义':'#96502d','死亡身后':'#6f6a63','其他':'#9d9a8d'};
const relCatColor=c=>REL_CAT_COLORS[c]||'#9d9a8d';
const eventCatColor=c=>EVENT_CAT_COLORS[c]||'#9d9a8d';
const catBadge=(c,color)=>`<span class="cat-tag" style="--cat:${color}">${esc(c)}</span>`;
const $=s=>document.querySelector(s);
const displayText=value=>String(value==null?'':value).replace(/[\u2192\u21E2\u21D2\u279C\u279D\u279E]/g,'至').replace(/\u2190/g,'来自').replace(/\u2194/g,'关联');
const esc=value=>displayText(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pageSize=36;
const state={dynastyEra:'',voyages:false,view:'overview',locMode:'index',locPage:1,locQuery:'',locRegion:'全部区域',chapterPage:1,distributionPage:1,distributionPart:'全部七部',distributionSort:'order',visualPart:'全部',visualPerson:'',netMode:'ego',charPage:1,charQuery:'',charPart:'',charFaction:'全部势力',charMinor:false,eventPage:1,eventQuery:'',eventType:'全部类型',eventCategory:'全部类别',relationPage:1,relationQuery:'',relationCategory:'全部类别',timelinePage:1,timelineCategory:'全部类别',printMode:null,rendered:{}};
const metrics=DATA.metrics;
const chapterLabel=key=>DATA.chapters[key]?.title||key;
const chapterChips=items=>(items||[]).slice(0,6).map(x=>`<span class="source-chip" title="${esc(x.title)}">${esc(x.title)}</span>`).join('')+((items||[]).length>6?`<span class="source-chip">+${items.length-6}章</span>`:'');
const pager=(page,total,size=pageSize)=>{const pages=Math.max(1,Math.ceil(total/size));return `<div class="pagination"><button data-page="prev" ${page<=1?'disabled':''}>上一页</button><span class="page-label">第 ${page} / ${pages} 页 · ${total} 条</span><button data-page="next" ${page>=pages?'disabled':''}>下一页</button></div>`};
const slicePage=(list,page)=>list.slice((page-1)*pageSize,page*pageSize);
function setView(view){state.view=view;document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id===view));document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x.dataset.view===view));if(!state.rendered[view]){({overview:renderOverview,distribution:renderDistribution,visuals:renderVisuals,locations:renderLocations,map:renderMap,characters:renderCharacters,events:renderEvents,relations:renderRelations,timeline:renderTimeline,dynasty:renderDynasty,chronicle:renderChronicle}[view])();state.rendered[view]=true;}if(view==='map'&&mapInstance){setTimeout(()=>mapInstance.invalidateSize(),60)}if(view==='visuals'&&state.netMode==='full'){setTimeout(()=>renderFullGraph(),30)}window.scrollTo(0,0)}
document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
document.addEventListener('click',e=>{const opener=e.target.closest('[data-open-view]');if(opener)setView(opener.dataset.openView)});
/* 翻面卡：全局委托一次，避免每次渲染人物页重复绑定导致点击失效 */
document.addEventListener('click',e=>{const flip=e.target.closest('[data-flip]');if(flip){e.preventDefault();const card=flip.closest('.character-card');if(card)card.classList.toggle('flip')}});
function openDetail(title,html){$('#dialogTitle').textContent=title;$('#dialogContent').innerHTML=html;$('#detailDialog').showModal()}
$('#dialogClose').addEventListener('click',()=>$('#detailDialog').close());
$('#detailDialog').addEventListener('click',e=>{if(e.target.id==='detailDialog')$('#detailDialog').close()});
const voyageToggleEl=$('#voyageToggle');if(voyageToggleEl){voyageToggleEl.addEventListener('change',e=>{state.voyages=e.target.checked;renderMap()})}
function renderOverview(){
 $('#headerStat').textContent=`${metrics.chapters}章 · ${metrics.characters}人 · ${metrics.events}件事件 · ${metrics.relations}条关系`;
 $('#overview').innerHTML=`<div class="section-head"><div><h2>知识库总览</h2><p>${esc(DATA.scopeLabel)} · 抽取结果与人工整理的统一出口</p></div><span class="status draft">结果仍需史料核验</span></div><div class="summary-hero"><div class="hero-copy"><h2>${esc(DATA.scopeLabel)}</h2><p>从章节、人物、地点、事件、关系和时间六个入口查看同一份结构化数据。每条记录都保留来源章节，未定位地点与未知年份不会被静默丢弃。</p><div class="hero-note">来源章节 ${metrics.chapters} · 已定位地点 ${metrics.locatedLocations}/${metrics.locations} · 有数值年份事件 ${metrics.timedEvents}/${metrics.events}</div></div><div class="metric-grid"><div class="metric"><span class="value">${metrics.characters}</span><span class="label">人物实体</span></div><div class="metric"><span class="value">${metrics.locations}</span><span class="label">地点实体</span></div><div class="metric"><span class="value">${metrics.events}</span><span class="label">事件实体</span></div><div class="metric"><span class="value">${metrics.relations}</span><span class="label">关系记录</span></div></div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">数据状态</h2><p>输出口径明确区分实体总量、已定位数量和待核验记录。</p></div></div><div class="quality-grid"><div class="quality"><strong>${metrics.locatedLocations}/${metrics.locations} 个地点已定位</strong><span>其余地点仍可在地点索引和章节视图中查看</span></div><div class="quality"><strong>${metrics.unknownEvents} 件事件年份待考</strong><span>保留在事件索引，不会从结果中消失</span></div><div class="quality"><strong>${metrics.relations} 条关系完整保留</strong><span>关系索引支持分页查看，不在人物卡中截断</span></div><div class="quality"><strong>章节来源可追溯</strong><span>人物、地点、事件和关系均关联章节标题</span></div></div></div>`;
 $('#overview').insertAdjacentHTML('beforeend', distributionTeaser());
 $('#overview').insertAdjacentHTML('beforeend', cleaningPanel());
}
function cleaningPanel(){const c=DATA.cleaning||{};if(!c.relation_categories&&!c.person_merged_names)return '';const relTotal=Object.values(c.relation_categories||{}).reduce((a,b)=>a+b,0)||1;const evTotal=Object.values(c.event_categories||{}).reduce((a,b)=>a+b,0)||1;const relSegs=Object.entries(c.relation_categories||{}).map(([k,v])=>`<span style="width:${(v*100/relTotal).toFixed(2)}%;background:${relCatColor(k)}" title="${esc(k)} ${v}条"></span>`).join('');const evSegs=Object.entries(c.event_categories||{}).map(([k,v])=>`<span style="width:${(v*100/evTotal).toFixed(2)}%;background:${eventCatColor(k)}" title="${esc(k)} ${v}件"></span>`).join('');const relLegend=Object.entries(c.relation_categories||{}).map(([k,v])=>`<span><i class="cat-dot" style="--cat:${relCatColor(k)};margin-right:4px"></i>${esc(k)} ${v}</span>`).join('');const evLegend=Object.entries(c.event_categories||{}).map(([k,v])=>`<span><i class="cat-dot" style="--cat:${eventCatColor(k)};margin-right:4px"></i>${esc(k)} ${v}</span>`).join('');const merged=(c.person_merged_names||[]).map(n=>`<span class="source-chip">${esc(n)}</span>`).join('')||'<span class="muted">本轮无合并</span>';return `<div class="panel"><div class="section-head"><div><h2 style="font-size:18px">数据清洗与分类</h2><p>同一人物异名、同城古地名已在聚合层合并；关系与事件的自由文本标签归入固定类别。</p></div><span class="status">聚合层处理</span></div><div class="clean-grid"><div class="clean-card"><strong>人物同名合并 ${c.person_merged_names?c.person_merged_names.length:0} 组</strong><span>异名并入规范名，章节与别名保留</span><div class="clean-chips">${merged}</div></div><div class="clean-card"><strong>地点同城合并 ${Object.keys(c.location_merge_groups||{}).length} 组 · 自环剔除 ${c.selfloop_dropped||0} 条</strong><span>${Object.entries(c.location_merge_groups||{}).map(([k,v])=>esc(v.join('、'))+'归入'+esc(k)).join('；')||'无'}</span></div><div class="clean-card"><strong>关系类别归一 ${relTotal} 条</strong><div class="cat-dist">${relSegs}</div><div class="cat-legend">${relLegend}</div></div><div class="clean-card"><strong>事件类别归一 ${evTotal} 件</strong><div class="cat-dist">${evSegs}</div><div class="cat-legend">${evLegend}</div></div></div></div>`;}
function distributionTeaser(){const d=DATA.distribution,s=d.stats,total=s.total,highest=[...d.chapters].sort((a,b)=>b.density-a.density)[0],lowest=[...d.chapters].sort((a,b)=>a.density-b.density)[0];return `<div class="panel distribution-teaser"><div class="section-head"><div><h2 style="font-size:18px">抽取分布诊断</h2><p>${esc(d.judgement.overall)} 详细分部、章节、密度和层级结构见“分布”。</p></div><button class="action" data-open-view="distribution">查看分布</button></div><div class="distribution-stat-grid"><div class="distribution-stat"><strong>CV ${total.cv}</strong><span>章节总抽取量的相对离散度</span></div><div class="distribution-stat"><strong>密度 ${s.density.cv}</strong><span>每万字密度的相对离散度</span></div><div class="distribution-stat"><strong>${esc(highest.title)}</strong><span>最高密度 ${highest.density}/万字</span></div><div class="distribution-stat"><strong>${esc(lowest.title)}</strong><span>最低密度 ${lowest.density}/万字</span></div></div></div>`}
function renderDistribution(){const d=DATA.distribution,s=d.stats,labels={characters:'人物',locations:'地点',events:'事件',relations:'关系'},colors={characters:'legend-character',locations:'legend-location',events:'legend-event',relations:'legend-relation'},sortLabels={order:'原书章节顺序',total:'总量从高到低',density:'密度从高到低',characters:'人物数从高到低',locations:'地点数从高到低',events:'事件数从高到低',relations:'关系数从高到低'};const chapterRows=d.chapters.map((item,index)=>({...item,_index:index}));const filtered=chapterRows.filter(item=>state.distributionPart==='全部七部'||item.partKey===state.distributionPart);const sorted=[...filtered].sort((a,b)=>{if(state.distributionSort==='order')return a._index-b._index;return b[state.distributionSort]-a[state.distributionSort]||a._index-b._index});const distPageSize=12;const page=sorted.slice((state.distributionPage-1)*distPageSize,state.distributionPage*distPageSize);const maxPart=Math.max(...d.parts.map(x=>x.total),1),maxChapter=Math.max(...chapterRows.map(x=>x.total),1),maxDensity=Math.max(...chapterRows.map(x=>x.density),1);const segment=(item,key,extra='')=>`<span class="${extra||'part-segment'} ${colors[key]}" style="width:${item.total?item[key]*100/item.total:0}%" title="${labels[key]} ${item[key]}"></span>`;const parts=d.parts.map(item=>`<div class="part-row"><div class="part-label"><strong>${esc(item.part)}</strong><span>${item.chapters}章 · 占章节抽取量 ${item.share}%</span></div><div class="part-bar" style="width:${item.total*100/maxPart}%">${segment(item,'characters')}${segment(item,'locations')}${segment(item,'events')}${segment(item,'relations')}</div><div class="part-values">${item.total}</div><div class="part-density">${item.density}/万字</div></div>`).join('');const chapterItems=page.map(item=>`<div class="chapter-row"><div class="chapter-name"><strong title="${esc(item.title)}">${esc(item.title)}</strong><span>${esc(item.part)} · ${item.textLength.toLocaleString()}字</span></div><div class="chapter-bars"><div class="chapter-track" style="width:${item.total*100/maxChapter}%">${segment(item,'characters','chapter-segment legend-character')}${segment(item,'locations','chapter-segment legend-location')}${segment(item,'events','chapter-segment legend-event')}${segment(item,'relations','chapter-segment legend-relation')}</div><div class="density-track" title="每万字 ${item.density}"><span style="width:${item.density*100/maxDensity}%"></span></div></div><div class="chapter-value">${item.total}条</div><div class="chapter-density">${item.density}/万</div></div>`).join('')||'<div class="empty">没有匹配章节</div>';const eraByPart=DATA.eraByPart||[];const eraMax=Math.max(...eraByPart.map(r=>r.total),1);const eraLegend=(DATA.reigns||[]).map((r,i)=>`<span><i class="legend-dot" style="background:${reignColor(i)}"></i>${esc(r.era)}</span>`).join('')+'<span><i class="legend-dot" style="background:#9d9a8d"></i>明兴之前/甲申之后</span>';const eraRows=eraByPart.map(r=>`<div class="part-row"><div class="part-label"><strong>${esc(r.part)}</strong><span>可纪年事件 ${r.total} 件 · ${r.segCount} 个年号段</span></div><div class="part-bar" style="width:${r.total*100/eraMax}%">${r.segments.map(sg=>`<span class="part-segment" style="width:${sg.count*100/r.total}%;background:${sg.order===0||sg.order===99?'#9d9a8d':reignColor(sg.order-1)}" title="${esc(sg.era)} · ${sg.count} 件"></span>`).join('')}</div><div class="part-values">${r.total}</div><div class="part-density">${r.segCount}段</div></div>`).join('')||'<div class="empty">暂无可纪年事件</div>';const entities=d.layers.entities.map(item=>`<li>${esc(item.label)} ${item.count}个实体 · ${item.chapterTotal}章次抽取</li>`).join('');const evidence=d.layers.evidence.map(item=>`<li>${esc(item.label)} ${item.count} · ${esc(item.detail)}</li>`).join('');$('#distribution').innerHTML=`<div class="section-head"><div><h2>抽取分布与层级</h2><p>${esc(DATA.scopeLabel)} · 章节级原始抽取诊断，和全局实体结果分开计数。</p></div><span class="status draft">分布不等于质量结论</span></div><div class="distribution-intro"><div class="distribution-callout"><span class="signal">判断</span><h3>${esc(d.judgement.overall)}</h3><p>总体 CV ${s.total.cv}；地点 CV ${s.locations.cv}，密度 CV ${s.density.cv}。最高与最低密度相差 ${d.judgement.densityRatio} 倍，说明章节长度和内容类型都需要纳入解释。</p></div><div class="distribution-stat-grid"><div class="distribution-stat"><strong>${s.total.median}</strong><span>章节总量中位数 · P25 ${s.total.p25} / P75 ${s.total.p75}</span></div><div class="distribution-stat"><strong>${s.locations.cv}</strong><span>地点数 CV · 四类中最不均匀</span></div><div class="distribution-stat"><strong>${s.density.max}</strong><span>最高每万字密度</span></div><div class="distribution-stat"><strong>${s.density.min}</strong><span>最低每万字密度</span></div></div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">一、分部层</h2><p>横向长度按分部总抽取量共享尺度，条内按人物、地点、事件、关系组成。</p></div></div><div class="distribution-legend"><span><i class="legend-dot legend-character"></i>人物</span><span><i class="legend-dot legend-location"></i>地点</span><span><i class="legend-dot legend-event"></i>事件</span><span><i class="legend-dot legend-relation"></i>关系</span><span>右侧为总量 / 每万字密度</span></div><div class="distribution-scale"><span>分部总抽取量</span><span>最大 ${maxPart} 条</span></div><div class="part-list">${parts}</div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">二、章节层</h2><p>四类计数均为章节内唯一项；上条为总量，下条为每万字密度。</p></div></div><div class="toolbar"><label>部次</label><select id="distPart"><option>全部七部</option>${d.parts.map(x=>`<option value="${x.partKey}" ${state.distributionPart===x.partKey?'selected':''}>${esc(x.part)}</option>`).join('')}</select><label>排序</label><select id="distSort">${Object.entries(sortLabels).map(([key,label])=>`<option value="${key}" ${state.distributionSort===key?'selected':''}>${label}</option>`).join('')}</select><span class="muted grow">共 ${filtered.length} 章 · 总量条形共享尺度 ${maxChapter} 条 · 密度按正文长度折算</span></div><div class="chapter-header"><span>章节</span><span>总量 / 密度</span><span>总量</span><span>每万字</span></div><div class="chapter-list-dist">${chapterItems}</div>${pager(state.distributionPage,sorted.length,distPageSize)}</div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">三、结果层级</h2><p>从来源章节到实体、关系网络，再落到可回溯的证据入口。</p></div></div><div class="layer-flow"><div class="layer-node"><small>01 · SOURCE</small><strong>${esc(d.layers.source.label)}</strong><b>${d.layers.source.count}章</b><span>${esc(d.layers.source.detail)}</span></div><div class="layer-connector" aria-hidden="true"></div><div class="layer-node"><small>02 · ENTITIES</small><strong>实体抽取</strong><b>${d.layers.entities.length}类</b><ul class="layer-list">${entities}</ul></div><div class="layer-connector" aria-hidden="true"></div><div class="layer-node"><small>03 · NETWORK</small><strong>${esc(d.layers.network.label)}</strong><b>${d.layers.network.count}条</b><span>章节内合计 ${d.layers.network.chapterTotal} 条关系抽取。</span></div><div class="layer-connector" aria-hidden="true"></div><div class="layer-node"><small>04 · TRACE</small><strong>来源追溯</strong><b>${d.layers.evidence.length}类</b><ul class="layer-list">${evidence}</ul></div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:18px">四、分部 × 年号</h2><p>可纪年事件按来源分部与在位年号段堆叠；条宽按总量共享尺度，悬停查看各段件数。</p></div></div><div class="distribution-legend">${eraLegend}</div><div class="part-list">${eraRows}</div></div><div class="distribution-foot">口径说明：章节层按单章内唯一姓名、地点古名、事件名、关系三元组计数；实体层按合并后的全局实体计数，跨章节重复出现不会被误加成实体总数。</div></div>`;$('#distPart').addEventListener('change',e=>{state.distributionPart=e.target.value;state.distributionPage=1;renderDistribution()});$('#distSort').addEventListener('change',e=>{state.distributionSort=e.target.value;state.distributionPage=1;renderDistribution()});const root=$('#distribution');bindPaging(root,delta=>{state.distributionPage+=delta;renderDistribution()})}
function renderVisuals(){
 const visuals=DATA.visualizations,heat=visuals.characterHeatmap,evolution=visuals.eventTypeEvolution,network=visuals.relationNetwork;
 const partKeys=[...new Set(heat.chapters.map(x=>x.partKey))].sort((a,b)=>Number(a.slice(1))-Number(b.slice(1)));const partOptions=`<option value="全部" ${state.visualPart==='全部'?'selected':''}>全部范围</option>${partKeys.map(key=>`<option value="${key}" ${state.visualPart===key?'selected':''}>${esc(PARTS[key]||key)}</option>`).join('')}`;
 const chapters=heat.chapters.filter(x=>state.visualPart==='全部'||x.partKey===state.visualPart);const chapterSet=new Set(chapters.map(x=>x.key));const heatRows=heat.characters.map(person=>`<div class="heatmap-name" title="${esc(person.name)}"><span>${esc(person.name)}</span><small>${person.chapterCount}章</small></div>${chapters.map(ch=>{const present=person.chapterKeys.includes(ch.key);return `<button type="button" class="heatmap-cell ${present?'present':''} part-${ch.partKey}" aria-label="${esc(person.name)} · ${esc(ch.title)} · ${present?'出现':'未出现'}" title="${esc(person.name)} · ${esc(ch.title)} · ${present?'出现':'未出现'}"></button>`}).join('')}`).join('');
 const heatmap=heatRows||'<div class="network-empty">当前范围没有可展示人物。</div>';const maxHeatColumns=Math.max(chapters.length,1);const heatHeader=`<div class="heatmap-corner">人物 / 章节</div>${chapters.map((ch,index)=>`<div class="heatmap-chapter" title="${esc(ch.part)} · ${esc(ch.title)}">${String(index+1).padStart(2,'0')}</div>`).join('')}`;
 const visibleParts=evolution.parts.filter(x=>state.visualPart==='全部'||x.partKey===state.visualPart);const maxTotal=Math.max(...visibleParts.map(x=>x.total),1);const colorByType=type=>`--event-color:${eventCatColor(type)}`;const legend=evolution.types.map(type=>`<span class="event-legend-item"><i style="${colorByType(type)}"></i>${esc(type)}</span>`).join('');const evolutionRows=visibleParts.map(part=>`<div class="evolution-row"><div class="evolution-label"><strong title="${esc(part.part)}">${esc(part.part)}</strong><span>${part.total}件事件</span></div><div class="evolution-track" title="${esc(part.part)} · ${part.total}件"><div class="evolution-fill" style="width:${part.total*100/maxTotal}%">${evolution.types.map(type=>`<span class="evolution-segment" style="width:${part.total?part.values[type]*100/part.total:0}%;background:${eventCatColor(type)}" title="${esc(type)} ${part.values[type]}件"></span>`).join('')}</div></div><div class="evolution-total">${part.total}</div></div>`).join('');
 const names=network.names;let selectedName=state.visualPerson&&network.byName[state.visualPerson]?state.visualPerson:(names[0]?.name||'');state.visualPerson=selectedName;const graph=network.byName[selectedName];const neighbors=(graph?.neighbors||[]).slice(0,12);const svgWidth=760,svgHeight=430,cx=svgWidth/2,cy=svgHeight/2,rx=290,ry=154;const positioned=neighbors.map((item,index)=>{const angle=-Math.PI/2+(Math.PI*2*index/Math.max(neighbors.length,1));return {...item,x:Math.round(cx+Math.cos(angle)*rx),y:Math.round(cy+Math.sin(angle)*ry)}});const networkLinks=positioned.map(item=>{const mx=Math.round((cx+item.x)/2),my=Math.round((cy+item.y)/2);return `<line class="network-link ${item.direction==='反向'?'incoming':''}" style="stroke:${relCatColor(item.category)}" x1="${cx}" y1="${cy}" x2="${item.x}" y2="${item.y}"><title>${esc(item.category)} · ${esc(item.direction)} · ${esc(item.relation)} · ${item.relationCount}条来源</title></line><text class="network-edge-label" x="${mx}" y="${my-5}">${esc(item.direction)}</text><text class="network-edge-label" x="${mx}" y="${my+8}">${esc(item.relation.length>12?item.relation.slice(0,12)+'...':item.relation)}</text>`}).join('');const networkNodes=positioned.map(item=>`<g><circle class="network-node" cx="${item.x}" cy="${item.y}" r="28"><title>${esc(item.name)} · ${item.chapterCount}章 · ${item.relationCount}条来源</title></circle><text class="network-label" x="${item.x}" y="${item.y+4}">${esc(item.name.length>6?item.name.slice(0,5)+'...':item.name)}</text></g>`).join('');const networkSvg=selectedName?`<svg class="network-svg" viewBox="0 0 ${svgWidth} ${svgHeight}" role="img" aria-label="${esc(selectedName)}的人物关系网络"><g>${networkLinks}</g><g><circle class="network-node center" cx="${cx}" cy="${cy}" r="42"><title>${esc(graph.center.name)} · ${graph.center.chapterCount}章 · ${graph.center.relationCount}条关系</title></circle><text class="network-label center" x="${cx}" y="${cy+4}">${esc(selectedName.length>7?selectedName.slice(0,6)+'...':selectedName)}</text></g><g>${networkNodes}</g></svg>`:'<div class="network-empty">当前范围没有可展示关系的人物。</div>';
 $('#visuals').innerHTML=`<div class="section-head"><div><h2>图谱：从章节分布到人物网络</h2><p>${esc(DATA.scopeLabel)} · 只展示高频人物、归一后的事件类别和核心人物邻域，保留原始数据的可读结构。</p></div><span class="status draft">图形用于发现线索</span></div><div class="visual-toolbar"><label for="visualPart">范围</label><select id="visualPart">${partOptions}</select><span class="visual-note">热力图按章节顺序排列；颜色和线型均有文字说明。</span></div><div class="visuals-stack"><section class="panel visuals-panel"><div class="section-head"><div><h3>一、人物出场轨迹</h3><p>纵轴为章节覆盖度最高的 24 位人物，横轴为当前范围内的章节序号；深色格表示该人物在该章有记录。</p></div><span class="visual-note">${heat.characters.length} 人 · ${chapters.length} 章</span></div><div class="heatmap-wrap"><div class="heatmap-grid" style="--heatmap-columns:${maxHeatColumns}">${heatHeader}${heatmap}</div></div><div class="heatmap-legend"><span><i class="heatmap-key present"></i>有出场记录</span><span><i class="heatmap-key empty"></i>无出场记录</span><span>人物行按章节覆盖度排序</span></div></section><section class="panel visuals-panel"><div class="section-head"><div><h3>二、事件类型演变</h3><p>各分部共享同一尺度；条形长度代表该部事件总量，内部颜色表示归一后的事件类别。</p></div><span class="visual-note">${visibleParts.length} 个分部 · ${evolution.types.length} 类</span></div><div class="event-legend">${legend}</div><div class="evolution-list">${evolutionRows||'<div class="network-empty">当前范围没有事件。</div>'}</div></section><section class="panel visuals-panel"><div class="section-head"><div><h3>三、核心人物关系网络</h3><p>切换查看：中心人物邻域，或全书人物关系总图（力导向布局，点越大关系越多）。</p></div></div><div class="network-controls"><label for="netMode">关系视图</label><select id="netMode"><option value="ego" ${state.netMode==='ego'?'selected':''}>中心人物</option><option value="full" ${state.netMode==='full'?'selected':''}>全书版本</option></select><span class="muted grow" id="netModeNote"></span></div><div id="egoNet"><div class="network-controls"><label for="visualPerson">中心人物</label><select id="visualPerson">${names.map(item=>`<option value="${esc(item.name)}" ${item.name===selectedName?'selected':''}>${esc(item.name)} · ${item.relationCount}条关系 · ${item.chapterCount}章</option>`).join('')}</select></div>${graph?`<div class="network-summary"><span>中心：<strong>${esc(graph.center.name)}</strong></span><span>覆盖 ${graph.center.chapterCount} 章</span><span>关系记录 ${graph.center.relationCount} 条</span><span>展示邻居 ${neighbors.length} 人</span></div><div class="cat-legend">${(DATA.relationCategories||[]).map(c=>`<span><i class="cat-dot" style="--cat:${relCatColor(c)};margin-right:4px"></i>${esc(c)}</span>`).join('')}</div>${networkSvg}`:'<div class="network-empty">暂无关系网络数据。</div>'}</div><div id="fullNet" style="display:${state.netMode==='full'?'block':'none'}"><div class="network-summary" id="fullSummary"></div><canvas id="fullGraph" class="network-svg full-graph-canvas"></canvas><div id="fullTip" class="full-graph-tip-box"></div><div class="cat-legend" id="fullLegend"></div><p class="full-graph-tip">滚轮缩放 · 拖拽平移 · 点击节点高亮其邻域 · 点击空白复位</p></div></section></div>`;
 $('#visualPart').addEventListener('change',event=>{state.visualPart=event.target.value;renderVisuals()});$('#visualPerson').addEventListener('change',event=>{state.visualPerson=event.target.value;renderVisuals()});
const nmEl=$('#netMode');if(nmEl){nmEl.addEventListener('change',e=>{state.netMode=e.target.value;const ego=$('#egoNet'),full=$('#fullNet');if(state.netMode==='full'){ego.style.display='none';full.style.display='block';renderFullGraph()}else{ego.style.display='block';full.style.display='none';stopFullSim();}});if(state.netMode==='full'){renderFullGraph()}}
}
function factionColor(tier){const palette=['#8d3025','#476b86','#527b5c','#b88b35','#6d688c','#a24b55','#3d7a7a','#9a6b2f','#7a5ca8','#4f7d3a','#b0466f','#356f9c','#8a6d2b','#5c7a3a','#9c5a3a'];let h=0;for(let i=0;i<tier.length;i++){h=(h*31+tier.charCodeAt(i))>>>0}return palette[h%palette.length]}
let fullT={k:1,tx:0,ty:0};
function applyFullTransform(){if(fullCanvas)drawFull()}
function fgByName(n){if(!_fgCache){_fgCache={};(DATA.relationGraphFull.nodes||[]).forEach(x=>{_fgCache[x.name]=x})}return _fgCache[n]}
function drawFull(){
  const g=DATA.relationGraphFull;if(!g||!g.nodes||!g.nodes.length)return;
  const ctx=fullCtx;ctx.save();ctx.setTransform(fullDpr,0,0,fullDpr,0,0);ctx.clearRect(0,0,fullCssW,fullCssH);
  const k=fullT.k,tx=fullT.tx,ty=fullT.ty;const hl=fullHighlight;const inc=new Set();
  const S=fullSim?fullSim.nodes:null;
  if(hl){inc.add(hl);g.links.forEach(l=>{if(l.source===hl)inc.add(l.target);if(l.target===hl)inc.add(l.source)});}
  g.links.forEach(l=>{const a=S?S[fullSim.ix[l.source]]:fgByName(l.source);const b=S?S[fullSim.ix[l.target]]:fgByName(l.target);if(!a||!b)return;const ax=a.x*k+tx,ay=a.y*k+ty,bx=b.x*k+tx,by=b.y*k+ty;let op=0.5,w=Math.min(0.6+l.count*0.35,3.2);if(hl){const on=(l.source===hl||l.target===hl);op=on?0.95:0.05;w=on?Math.min(w+0.8,4):w;}ctx.strokeStyle=relCatColor(l.category);ctx.globalAlpha=op;ctx.lineWidth=w;ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(bx,by);ctx.stroke();});
  ctx.globalAlpha=1;
  g.nodes.forEach((nd,i)=>{const s=S?S[i]:nd;const x=s.x*k+tx,y=s.y*k+ty,r=Math.max(s.r*k,2.2);let op=1;if(hl){op=inc.has(nd.name)?1:0.12;}ctx.globalAlpha=op;ctx.fillStyle=factionColor(nd.tier);ctx.beginPath();ctx.arc(x,y,r,0,6.2832);ctx.fill();ctx.lineWidth=0.8;ctx.strokeStyle='#fffdf9';ctx.stroke();if(nd.degree>=10&&(!hl||inc.has(nd.name))){ctx.globalAlpha=op;ctx.fillStyle='#443a32';ctx.font='11px "Microsoft YaHei","PingFang SC",sans-serif';ctx.textAlign='center';ctx.fillText(nd.name.length>6?nd.name.slice(0,6)+'…':nd.name,x,y-r-4);}});
  ctx.globalAlpha=1;ctx.restore();
}
/* 实时力模拟：网格加速斥力 + 弹簧 + 中心引力 + 微抖动（轻微飘动） */
let fullSim=null,fullReduceMotion=false,_fullBound=false,_fullResizeBound=false;
function sizeFullCanvas(){if(!fullCanvas)return;const g=DATA.relationGraphFull;if(!g)return;const cssW=fullCanvas.parentElement.clientWidth||800;const cssH=Math.max(320,Math.min(cssW*(g.height/g.width),cssW*1.15));fullCssW=cssW;fullCssH=cssH;fullDpr=window.devicePixelRatio||1;fullCanvas.style.height=cssH+'px';fullCanvas.width=Math.round(cssW*fullDpr);fullCanvas.height=Math.round(cssH*fullDpr);fullCanvas.style.width=cssW+'px';const s=cssW/g.width;fullT={k:s,tx:0,ty:0};if(!_fullResizeBound){_fullResizeBound=true;let rt=null;window.addEventListener('resize',()=>{if(!fullCanvas)return;clearTimeout(rt);rt=setTimeout(()=>{sizeFullCanvas();drawFull();},120);});}}
function initFullSim(){const g=DATA.relationGraphFull;if(!g||!g.nodes||!g.nodes.length){fullSim=null;return;}const nodes=g.nodes.map(nd=>({name:nd.name,x:nd.x,y:nd.y,vx:0,vy:0,r:nd.r,degree:nd.degree,faction:nd.faction,tier:nd.tier,role:nd.role,fixed:false}));const ix={};nodes.forEach((n,i)=>ix[n.name]=i);const links=g.links.map(l=>({a:ix[l.source],b:ix[l.target],category:l.category,count:l.count}));fullSim={nodes,ix,links,w:g.width,h:g.height,alpha:1,alphaTarget:0,raf:null,dragIdx:-1,reduced:fullReduceMotion};}
function fullStep(){const S=fullSim;if(!S)return;const N=S.nodes,n=N.length;const k=24,rep=160,spring=0.02,gravity=0.018,cx=S.w/2,cy=S.h/2,alpha=S.alpha;const thermal=S.reduced?0:0.22;const cell=k*4;const grid=new Map();for(let i=0;i<n;i++){const nd=N[i];const gx=Math.floor(nd.x/cell),gy=Math.floor(nd.y/cell);const key=gx+'|'+gy;let arr=grid.get(key);if(!arr){arr=[];grid.set(key,arr);}arr.push(i);}for(let i=0;i<n;i++){const a=N[i];if(a.fixed)continue;let fx=0,fy=0;const gx=Math.floor(a.x/cell),gy=Math.floor(a.y/cell);for(let ox=-1;ox<=1;ox++)for(let oy=-1;oy<=1;oy++){const arr=grid.get((gx+ox)+'|'+(gy+oy));if(!arr)continue;for(let q=0;q<arr.length;q++){const j=arr[q];if(j===i)continue;const b=N[j];let dx=a.x-b.x,dy=a.y-b.y;let d2=dx*dx+dy*dy;if(d2<1e-3){dx=Math.random()-0.5;dy=Math.random()-0.5;d2=dx*dx+dy*dy+1e-3;}const d=Math.sqrt(d2);const f=rep/d2;fx+=dx/d*f;fy+=dy/d*f;}}fx+=(cx-a.x)*gravity;fy+=(cy-a.y)*gravity;a._fx=fx;a._fy=fy;}for(let e=0;e<S.links.length;e++){const l=S.links[e];const a=N[l.a],b=N[l.b];if(a.fixed&&b.fixed)continue;let dx=b.x-a.x,dy=b.y-a.y;let d=Math.sqrt(dx*dx+dy*dy)+1e-6;const f=(d-k)*spring;const fx=dx/d*f,fy=dy/d*f;if(!a.fixed){a._fx+=fx;a._fy+=fy;}if(!b.fixed){b._fx-=fx;b._fy-=fy;}}const damp=0.85,maxStep=12;for(let i=0;i<n;i++){const a=N[i];if(a.fixed){a.vx=0;a.vy=0;continue;}const jx=thermal?(Math.random()-0.5)*thermal:0;const jy=thermal?(Math.random()-0.5)*thermal:0;a.vx=(a.vx+a._fx*alpha+jx)*damp;a.vy=(a.vy+a._fy*alpha+jy)*damp;const sp=Math.hypot(a.vx,a.vy);if(sp>maxStep){a.vx*=maxStep/sp;a.vy*=maxStep/sp;}a.x+=a.vx;a.y+=a.vy;}S.alpha+=(S.alphaTarget-S.alpha)*0.02;if(S.alpha<0)S.alpha=0;}
function fullLoop(){if(!fullSim)return;fullStep();drawFull();if(fullSim.alpha<0.02&&fullSim.dragIdx<0){const r=fullSim.raf;fullSim.raf=null;if(r)cancelAnimationFrame(r);return;}fullSim.raf=requestAnimationFrame(fullLoop);}
function startFullSim(){if(!fullSim)initFullSim();if(fullSim&&!fullSim.raf){fullSim.raf=requestAnimationFrame(fullLoop);}}
function stopFullSim(){if(fullSim&&fullSim.raf){cancelAnimationFrame(fullSim.raf);fullSim.raf=null;}}
function renderFullGraph(){
  const g=DATA.relationGraphFull;const sum=document.getElementById('fullSummary'),legend=document.getElementById('fullLegend'),canvas=document.getElementById('fullGraph');
  if(!g||!g.nodes||!g.nodes.length){if(sum)sum.innerHTML='<span>当前范围没有可绘制的关系图。</span>';return;}
  fullReduceMotion=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  fullCanvas=canvas;fullCtx=canvas.getContext('2d');_fgCache=null;fullHighlight=null;
  sizeFullCanvas();
  legend.innerHTML=(DATA.relationCategories||[]).map(c=>`<span><i class="cat-dot" style="--cat:${relCatColor(c)};margin-right:4px"></i>${esc(c)}</span>`).join('')+`<span class="muted"> · 点大小=关系数，颜色=势力大类 · 可拖拽节点</span>`;
  sum.innerHTML=`<span>全书关系图：<strong>${g.stats.nodes}</strong> 名人物 · <strong>${g.stats.edges}</strong> 条关系</span><span>孤立人物 ${g.stats.isolated}</span>`;
  initFullSim();
  drawFull();
  if(!_fullBound){setupFullInteractions(canvas);_fullBound=true;}
  startFullSim();
}
function showFullNode(name){const g=DATA.relationGraphFull;const node=fgByName(name);if(!node)return;fullHighlight=name;const inc=new Set([name]);g.links.forEach(l=>{if(l.source===name)inc.add(l.target);if(l.target===name)inc.add(l.source)});const neigh=[...inc].filter(x=>x!==name);document.getElementById('fullSummary').innerHTML=`<span>已选：<strong>${esc(name)}</strong></span><span>${esc(node.faction||'势力待补')}</span><span>关系 ${node.degree} 条</span><span>邻域 ${neigh.length} 人</span>`;drawFull();}
function resetFullHighlight(){fullHighlight=null;const g=DATA.relationGraphFull;if(g)document.getElementById('fullSummary').innerHTML=`<span>全书关系图：<strong>${g.stats.nodes}</strong> 名人物 · <strong>${g.stats.edges}</strong> 条关系</span><span>孤立人物 ${g.stats.isolated}</span>`;drawFull();}
function setupFullInteractions(canvas){
  const hit=(mx,my)=>{const arr=fullSim?fullSim.nodes:DATA.relationGraphFull.nodes;let best=-1,bd=1e9;for(let i=0;i<arr.length;i++){const nd=arr[i];const sx=nd.x*fullT.k+fullT.tx,sy=nd.y*fullT.k+fullT.ty;const d=Math.hypot(sx-mx,sy-my);const rr=Math.max(nd.r*fullT.k,2.2)+6;if(d<rr&&d<bd){bd=d;best=i;}}return best;};
  let panning=false,lx=0,ly=0,moved=false,dragIdx=-1;
  canvas.addEventListener('wheel',e=>{e.preventDefault();const rect=canvas.getBoundingClientRect();const mx=e.clientX-rect.left,my=e.clientY-rect.top;const f=e.deltaY<0?1.12:1/1.12;const nk=Math.min(Math.max(fullT.k*f,0.15),14);const r=nk/fullT.k;fullT.tx=mx-(mx-fullT.tx)*r;fullT.ty=my-(my-fullT.ty)*r;fullT.k=nk;drawFull();},{passive:false});
  canvas.addEventListener('pointerdown',e=>{const rect=canvas.getBoundingClientRect();const idx=hit(e.clientX-rect.left,e.clientY-rect.top);moved=false;lx=e.clientX;ly=e.clientY;if(idx>=0){dragIdx=idx;if(fullSim){const nd=fullSim.nodes[idx];nd.fixed=true;fullSim.dragIdx=idx;fullSim.alpha=Math.max(fullSim.alpha,0.6);fullSim.alphaTarget=0.6;}startFullSim();canvas.classList.add('dragging');if(canvas.setPointerCapture)try{canvas.setPointerCapture(e.pointerId);}catch(_){}}else{panning=true;canvas.classList.add('dragging');}});
  window.addEventListener('pointerup',()=>{if(dragIdx>=0&&fullSim){const nd=fullSim.nodes[dragIdx];nd.fixed=false;fullSim.dragIdx=-1;fullSim.alphaTarget=0;fullSim.alpha=Math.max(fullSim.alpha,0.35);}dragIdx=-1;panning=false;canvas.classList.remove('dragging');});
  canvas.addEventListener('pointermove',e=>{const rect=canvas.getBoundingClientRect();const mx=e.clientX-rect.left,my=e.clientY-rect.top;
    if(dragIdx>=0){const dx=e.clientX-lx,dy=e.clientY-ly;if(Math.abs(dx)>3||Math.abs(dy)>3)moved=true;const nd=fullSim.nodes[dragIdx];nd.x=(mx-fullT.tx)/fullT.k;nd.y=(my-fullT.ty)/fullT.k;nd.vx=dx/fullT.k;nd.vy=dy/fullT.k;lx=e.clientX;ly=e.clientY;fullSim.alpha=Math.max(fullSim.alpha,0.6);return;}
    if(panning){const dx=e.clientX-lx,dy=e.clientY-ly;if(Math.abs(dx)>3||Math.abs(dy)>3)moved=true;fullT.tx+=dx;fullT.ty+=dy;lx=e.clientX;ly=e.clientY;drawFull();return;}
    const idx=hit(mx,my);const tip=document.getElementById('fullTip');if(idx>=0){const nd=(fullSim?fullSim.nodes:fgByName(DATA.relationGraphFull.nodes[idx].name));canvas.style.cursor='grab';tip.style.display='block';tip.style.left=e.clientX+'px';tip.style.top=e.clientY+'px';tip.textContent=`${nd.name}${nd.faction?' · '+nd.faction:''}${nd.role?' · '+nd.role:''} · ${nd.degree}条关系`;}else{canvas.style.cursor='grab';tip.style.display='none';}});
  canvas.addEventListener('click',e=>{if(moved){moved=false;return;}const rect=canvas.getBoundingClientRect();const idx=hit(e.clientX-rect.left,e.clientY-rect.top);if(idx>=0){const name=(fullSim?fullSim.nodes[idx].name:DATA.relationGraphFull.nodes[idx].name);showFullNode(name);}else resetFullHighlight();});
}
let fullCanvas=null,fullCtx=null,fullDpr=1,fullCssW=0,fullCssH=0,fullHighlight=null,_fgCache=null;
function locationCard(item){const coords=item.lat!=null?`${Number(item.lat).toFixed(2)}, ${Number(item.lng).toFixed(2)}`:'未定位';return `<article class="location-card"><div class="card-head"><div><span class="card-title">${esc(item.ancient)}</span> <span class="tag">${esc(item.trace)}</span></div><span class="status ${item.status==='已定位'?'':'draft'}">${esc(item.status)}</span></div><div class="meta">今址：${esc(item.modern)}${item.mentionedAs?.length?`<br>别称：${esc(item.mentionedAs.join('、'))}`:''}</div><div class="meta">坐标：${esc(coords)} · ${esc(item.region)}</div>${item.directEvents.length?`<div class="meta"><b>直接关联事件：</b><ul class="event-list">${item.directEvents.slice(0,6).map(x=>`<li><button class="link-button" data-event-name="${esc(x)}">${esc(x)}</button></li>`).join('')}</ul></div>`:`<div class="meta">当前章节仅提及，未确认具体事件落点。</div>`}${item.relatedEventCount?`<div class="meta muted">同章另有 ${item.relatedEventCount} 件事件，未作为地点直接关联。</div>`:''}<div class="source-row">${chapterChips(item.chapters)}<button class="action" data-location-id="${item.id}">详情</button></div></article>`}
function bindPaging(root,callback){root.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{if(!b.disabled){callback(b.dataset.page==='next'?1:-1)}}))}
function renderLocations(){
 const all=DATA.locations.filter(x=>(!state.locQuery||`${x.ancient} ${x.modern} ${x.region}`.toLowerCase().includes(state.locQuery.toLowerCase()))&&(!state.locRegion||state.locRegion==='全部区域'||x.region===state.locRegion));
 const body=state.locMode==='index'?`<div class="data-grid">${slicePage(all,state.locPage).map(locationCard).join('')||'<div class="empty">没有匹配地点</div>'}</div>${pager(state.locPage,all.length)}`:`<div class="chapter-list">${DATA.chapterLocations.slice((state.chapterPage-1)*12,state.chapterPage*12).map(ch=>`<article class="chapter-block"><h3>${esc(ch.title)} <span class="muted">${esc(ch.part)}</span></h3>${ch.items.map(item=>`<div class="chapter-place"><strong>${esc(item.ancient)}</strong><span>${esc(item.modern)} · <span class="status ${item.status==='已定位'?'':'draft'}">${esc(item.status)}</span>${item.directEvents.length?`<br><span class="muted">${item.directEvents.slice(0,4).map(esc).join(' · ')}</span>`:''}</span></div>`).join('')}</article>`).join('')}</div>${pager(state.chapterPage,DATA.chapterLocations.length,12)}`;
 $('#locations').innerHTML=`<div class="section-head"><div><h2>地点索引</h2><p>${metrics.locations} 个地点实体，${metrics.locatedLocations} 个已定位；直接关联事件与同章提及分开显示。</p></div></div><div class="panel"><div class="subnav"><button data-loc-mode="index" class="${state.locMode==='index'?'active':''}">地点索引</button><button data-loc-mode="chapter" class="${state.locMode==='chapter'?'active':''}">按章节</button></div><div class="toolbar"><label>搜索</label><input class="search" id="locQuery" value="${esc(state.locQuery)}" placeholder="古名、今址或区域"><label>区域</label><select id="locRegion"><option>全部区域</option>${[...new Set(DATA.locations.map(x=>x.region))].sort().map(x=>`<option ${x===state.locRegion?'selected':''}>${esc(x)}</option>`).join('')}</select></div>${body}</div>`;
 $('#locQuery').addEventListener('input',e=>{state.locQuery=e.target.value;state.locPage=1;renderLocations()});$('#locRegion').addEventListener('change',e=>{state.locRegion=e.target.value;state.locPage=1;renderLocations()});document.querySelectorAll('[data-loc-mode]').forEach(b=>b.addEventListener('click',()=>{state.locMode=b.dataset.locMode;renderLocations()}));
 const root=$('#locations');bindPaging(root,delta=>{if(state.locMode==='index')state.locPage+=delta;else state.chapterPage+=delta;renderLocations()});
 root.querySelectorAll('[data-location-id]').forEach(b=>b.addEventListener('click',()=>{const x=DATA.locations.find(y=>y.id===b.dataset.locationId);openDetail(x.ancient,locationDetailHTML(x,'event'))}));
 root.querySelectorAll('[data-event-name]').forEach(b=>b.addEventListener('click',()=>{const event=DATA.events.find(x=>x.name===b.dataset.eventName);if(event)showEvent(event)}));
}
function showEvent(event){openDetail(event.name,`<div class="detail-grid"><div class="detail-block"><strong>时间</strong><p>${esc(event.year||'年份待考')}${event.year_source?` <span class="src-tag">${event.year_approx?'约·':''}来源：${esc(event.year_source)}</span>`:''}${event.year_note?` <span class="src-note">（${esc(event.year_note)}）</span>`:''}</p></div><div class="detail-block"><strong>类别</strong><p>${catBadge(event.category,eventCatColor(event.category))}</p></div><div class="detail-block"><strong>原类型</strong><p>${esc(event.type)}</p></div><div class="detail-block"><strong>地点</strong><p>${esc(event.location)}</p></div><div class="detail-block"><strong>参与者</strong><p>${esc(event.participants.join('、')||'未标注')}</p></div><div class="detail-block detail-wide"><strong>来源章节</strong><div class="source-row">${chapterChips(event.sources)}</div></div></div>`)}
function locationDetailHTML(x, evtAttr){
  const evs=(x.directEvents||[]).map(n=>DATA.events.find(e=>e.name===n)).filter(Boolean);
  const people=[...new Set(evs.flatMap(e=>e.participants||[]))];
  const eventsHtml=evs.length?`<ul class="event-list">${evs.map(e=>`<li><button class="link-button" data-${evtAttr}="${esc(e.name)}">${esc(e.name)}</button> · ${esc(e.year||'年份待考')}</li>`).join('')}</ul>`:`<p class="muted">当前范围仅提及，书中未确认具体事件落点。</p>`;
  const relEvs=x.relatedEvents||[];
  const relatedHtml=relEvs.length?`<div class="meta"><b>同章上下文事件（${relEvs.length}）</b></div><ul class="event-list">${relEvs.slice(0,15).map(n=>`<li><button class="link-button" data-${evtAttr}="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul><p class="muted">书中同章提及，非本地点直接落点（可作圣地巡礼上下文）</p>`:`<p class="muted">同章亦无其它事件记录。</p>`;
  const relPeople=x.relatedPeople||[];
  const ph=people.length?esc(people.slice(0,15).join('、')):(relPeople.length?esc(relPeople.slice(0,15).join('、')):'无（或未标注）');
  const phNote=people.length?'':'<span class="muted">（来自同章上下文事件）</span>';
  return `<div class="detail-grid"><div class="detail-block"><strong>今址</strong><p>${esc(x.modern)}</p></div><div class="detail-block"><strong>书中身份</strong><p>${esc(x.trace)}</p></div><div class="detail-block"><strong>别称</strong><p>${esc(x.mentionedAs.join('、')||'无')}</p></div><div class="detail-block"><strong>坐标</strong><p>${x.lat==null?'未定位':`${x.lat}, ${x.lng}`}</p></div><div class="detail-block detail-wide"><strong>书中直接关联事件（${evs.length}）</strong>${eventsHtml}${relatedHtml}</div><div class="detail-block detail-wide"><strong>书中涉及人物 ${phNote}</strong><p>${ph}</p></div><div class="detail-block detail-wide"><strong>来源章节</strong><div class="source-row">${chapterChips(x.chapters)}</div></div><div class="detail-block detail-wide"><strong>核验备注</strong><p>${esc(x.note||'暂无')}</p></div></div>`;
}
function bindEventNameClicks(){const dlg=$('#detailDialog');if(!dlg)return;dlg.querySelectorAll('[data-event-name]').forEach(b=>b.addEventListener('click',()=>{const ev=DATA.events.find(e=>e.name===b.dataset.eventName);if(ev)showEvent(ev)}))}
function showLocation(x){const html=locationDetailHTML(x,'loc');const dock=$('#locDock');dock.innerHTML=`<div class="dock-head"><h3>${esc(x.ancient)}</h3><button class="dock-close" id="locDockClose">关闭</button></div>${html}`;dock.hidden=false;const closeDock=()=>{dock.hidden=true;if(mapInstance)setTimeout(()=>mapInstance.invalidateSize(),60)};$('#locDockClose').addEventListener('click',closeDock);dock.querySelectorAll('[data-loc-event]').forEach(b=>b.addEventListener('click',()=>{const ev=DATA.events.find(e=>e.name===b.dataset.locEvent);if(ev)showEvent(ev)}));if(mapInstance)setTimeout(()=>mapInstance.invalidateSize(),60)}
let mapInstance=null;function renderMap(){const locations=DATA.locations.filter(x=>x.lat!=null&&x.lng!=null);const voyage=(DATA.voyages&&DATA.voyages.points&&DATA.voyages.points.length>=2)?DATA.voyages:null;const tw=$('#voyageToggleWrap');if(tw){tw.style.display=voyage?'':'none';const vn=$('#voyageNote');if(vn){vn.textContent=voyage?`${voyage.points.length} 个停靠点 · ${esc(voyage.note||'')}`:''}}$('#mapNote').textContent=`已定位 ${locations.length}/${DATA.locations.length} 个地点。${window.L?'地图瓦片来自 OpenStreetMap，需联网加载。':'当前为离线点位图，地图瓦片未加载。'}`;const box=$('#mapBox');if(mapInstance){mapInstance.remove();mapInstance=null}box.innerHTML='';if(window.L){const map=L.map(box).setView([34.5,113],4);mapInstance=map;L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© OpenStreetMap'}).addTo(map);locations.forEach(x=>{const m=L.circleMarker([x.lat,x.lng],{radius:6,color:'#8d3025',fillColor:'#b94a37',fillOpacity:.85}).addTo(map);m.bindTooltip(esc(x.ancient));m.on('click',()=>showLocation(x))});if(voyage&&state.voyages){const pts=voyage.points.map(p=>[p.lat,p.lng]);L.polyline(pts,{color:'#b88b35',weight:3,dashArray:'7 6',opacity:.9}).addTo(map).bindPopup(`<b>${esc(voyage.name)}</b><br>${esc(voyage.note||'')}`);voyage.points.forEach((p,i)=>{L.circleMarker([p.lat,p.lng],{radius:8,color:'#8a6a1f',fillColor:'#e8c872',fillOpacity:.95,weight:2}).addTo(map).bindPopup(`<b>${i+1}. ${esc(p.name)}</b>`).bindTooltip(String(i+1),{permanent:true,direction:'top',className:'voyage-num',offset:[0,-9]})})}setTimeout(()=>map.invalidateSize(),100)}else{const points=locations;const proj=x=>{const px=Math.max(30,Math.min(970,(x.lng-73)/62*940)),py=Math.max(30,Math.min(490,(54-x.lat)/36*460));return[px,py]};let route='';if(voyage&&state.voyages){const vs=voyage.points.map(proj);route=`<polyline points="${vs.map(v=>v.join(',')).join(' ')}" fill="none" stroke="#b88b35" stroke-width="2" stroke-dasharray="6 5"/>`+voyage.points.map((p,i)=>{const[px,py]=proj(p);return `<circle cx="${px}" cy="${py}" r="7" fill="#e8c872" stroke="#8a6a1f" stroke-width="2"/><text x="${px}" y="${py+3}" text-anchor="middle" font-size="9" fill="#5f4a14" font-weight="bold">${i+1}</text><title>${i+1}. ${esc(p.name)}</title>`}).join('')}box.innerHTML=`<svg class="fallback-map" viewBox="0 0 1000 520" role="img" aria-label="地点坐标图"><rect width="1000" height="520" fill="#e6eee7"/><path d="M80 440 Q280 280 480 350 T920 150" fill="none" stroke="#b8cbb8" stroke-width="80" opacity=".45"/>${route}${points.map(x=>{const[px,py]=proj(x);return `<circle cx="${px}" cy="${py}" r="5" fill="#8d3025" data-loc-ancient="${esc(x.ancient)}" style="cursor:pointer"><title>${esc(x.ancient)} · ${esc(x.modern)}（点击查看书中介绍）</title></circle>`}).join('')}</svg>`}box.querySelectorAll('[data-loc-ancient]').forEach(c=>c.addEventListener('click',()=>{const x=DATA.locations.find(y=>y.ancient===c.dataset.locAncient);if(x)showLocation(x)}));const t=$('#voyageToggle');if(t){t.onchange=()=>{state.voyages=t.checked;renderMap()}}}
function renderCharacters(){
 const factions=[...new Set(DATA.characters.map(x=>x.faction).filter(Boolean))].sort();const list=DATA.characters.filter(x=>(!state.charPart||x.chapters.some(k=>k.startsWith(state.charPart+'-')))&&(!state.charFaction||state.charFaction==='全部势力'||x.faction===state.charFaction)&&(!state.charQuery||`${x.name} ${x.faction} ${x.role} ${x.aliases.join(' ')} ${x.events.join(' ')}`.toLowerCase().includes(state.charQuery.toLowerCase()))&&(state.charMinor||x.chapters.length>1));const page=slicePage(list,state.charPage);$('#characters').innerHTML=`<div class="section-head"><div><h2>人物索引</h2><p>${metrics.characters} 个角色实体；默认按章节覆盖度排序，关系完整保留在详情中。</p></div></div><div class="panel"><div class="toolbar"><label>部次</label><select id="charPart"><option value="">全部七部</option>${Object.entries(PARTS).map(([k,v])=>`<option value="${k}" ${state.charPart===k?'selected':''}>${esc(v)}</option>`).join('')}</select><label>势力</label><select id="charFaction"><option>全部势力</option>${factions.map(x=>`<option ${state.charFaction===x?'selected':''}>${esc(x)}</option>`).join('')}</select><input class="search grow" id="charQuery" value="${esc(state.charQuery)}" placeholder="姓名、身份、别名或事件"><label style="display:inline-flex;gap:6px;align-items:center;color:var(--ink)"><input type="checkbox" id="charMinor" ${state.charMinor?'checked':''}>显示次要人物(仅1章)</label><button class="action" id="charReset">重置</button></div><div class="character-toolbar"><button class="mode active" data-char-mode="screen">屏幕卡</button><button class="mode" data-char-mode="front">打印正面</button><button class="mode" data-char-mode="back">打印背面</button><span class="muted" id="charCount">显示 ${page.length} / ${list.length} · 次要(仅1章) ${DATA.characters.filter(x=>x.chapters.length<=1).length} 人${state.charMinor?'':'（已折叠）'}</span></div><div id="charScreen" class="character-grid">${page.map(characterCard).join('')||'<div class="empty">没有匹配人物</div>'}</div><div id="printGuide" class="print-guide" style="display:none">当前筛选结果共 ${list.length} 张；打印页只在选择打印模式时生成。</div><div id="printArea" class="print-area"></div>${pager(state.charPage,list.length)}</div>`;
 $('#charPart').addEventListener('change',e=>{state.charPart=e.target.value;state.charPage=1;renderCharacters()});$('#charFaction').addEventListener('change',e=>{state.charFaction=e.target.value;state.charPage=1;renderCharacters()});$('#charQuery').addEventListener('input',e=>{state.charQuery=e.target.value;state.charPage=1;renderCharacters()});$('#charReset').addEventListener('click',()=>{state.charPart='';state.charFaction='全部势力';state.charQuery='';state.charPage=1;renderCharacters()});$('#charMinor').addEventListener('change',e=>{state.charMinor=e.target.checked;state.charPage=1;renderCharacters()});
 const root=$('#characters');bindPaging(root,delta=>{state.charPage+=delta;renderCharacters()});root.querySelectorAll('[data-char-mode]').forEach(b=>b.addEventListener('click',()=>{root.querySelectorAll('[data-char-mode]').forEach(x=>x.classList.remove('active'));b.classList.add('active');if(b.dataset.charMode==='screen'){root.querySelector('#charScreen').style.display='grid';root.querySelector('#printGuide').style.display='none';root.querySelector('#printArea').style.display='none'}else{root.querySelector('#charScreen').style.display='none';root.querySelector('#printGuide').style.display='block';root.querySelector('#printArea').style.display='block';renderPrint(b.dataset.charMode,list)}}));root.querySelectorAll('[data-char-detail]').forEach(b=>b.addEventListener('click',()=>{const x=DATA.characters.find(y=>y.name===b.dataset.charDetail);openDetail(x.name,`<div class="detail-grid"><div class="detail-block"><strong>身份</strong><p>${esc(x.role)}</p></div><div class="detail-block"><strong>势力</strong><p>${esc(x.faction||'未标注')}</p></div><div class="detail-block"><strong>生卒 / 籍贯</strong><p>${esc(x.life)} · ${esc(x.birth)}</p></div><div class="detail-block"><strong>状态</strong><p>${esc(x.status)}</p></div><div class="detail-block detail-wide"><strong>别名</strong><p>${esc(x.aliases.join('、')||'无')}</p></div><div class="detail-block detail-wide"><strong>涉及事件（${x.events.length}）</strong>${x.events.length?`<ul class="event-list">${x.events.slice(0,12).map(n=>`<li><button class="link-button" data-event-name="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul>`:`<p class="muted">书中未作为事件参与者出现。</p>`}</div><div class="detail-block detail-wide"><strong>同章上下文事件（${x.contextEvents.length}）</strong>${x.contextEvents.length?`<ul class="event-list">${x.contextEvents.slice(0,15).map(n=>`<li><button class="link-button" data-event-name="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul><p class="muted">书中同章提及，非本人物直接参与（可作关联线索）</p>`:`<p class="muted">同章亦无其它事件记录。</p>`}</div><div class="detail-block detail-wide"><strong>关系</strong><p>${x.relations.map(r=>`${esc(r.to)}（${esc(r.rel)}）`).join('、')||'无'}</p></div><div class="detail-block detail-wide"><strong>来源章节</strong><div class="source-row">${chapterChips(x.chapters.map(k=>({key:k,...DATA.chapters[k]})))}</div></div></div>`);bindEventNameClicks()}));
}
function characterCard(x){return `<article class="character-card"><div class="inner"><div class="face front"><h3>${esc(x.name)}</h3><span class="tag" style="margin-top:8px">${esc(x.faction||'势力待补')}</span><div class="summary">${esc(x.summary)}</div><div class="card-actions"><button data-flip>翻面</button><button data-char-detail="${esc(x.name)}">详情</button></div></div><div class="face back"><h3>${esc(x.name)}</h3><div class="meta"><b>身份：</b>${esc(x.role)}</div><div class="meta"><b>生卒：</b>${esc(x.life)} · <b>籍贯：</b>${esc(x.birth)}</div><div class="meta"><b>状态：</b>${esc(x.status)}</div><div class="meta"><b>事件：</b>${x.events.length?esc(x.events.slice(0,5).join('、')):`<span class="muted">${esc(x.contextEvents.slice(0,5).join('、')||'无')}</span> <span class="src-note">（同章提及）</span>`}</div><div class="meta"><b>关系：</b>${esc(x.relations.slice(0,5).map(r=>`${r.to}（${r.rel}）`).join('、')||'无')}</div><div class="card-actions"><button data-flip>翻面</button><button data-char-detail="${esc(x.name)}">详情</button></div></div></div></article>`}
function renderPrint(kind,list){const pages=[];for(let i=0;i<list.length;i+=9){const cards=list.slice(i,i+9).map(x=>kind==='front'?`<div class="print-card front"><div class="name">${esc(x.name)}</div><div class="text">${esc(x.summary)}</div></div>`:`<div class="print-card back"><div class="name">${esc(x.name)}</div><div>身份：${esc(x.role)}</div><div>势力：${esc(x.faction||'未标注')}</div><div>生卒：${esc(x.life)}</div><div>籍贯：${esc(x.birth)}</div><div>事件：${esc(x.events.slice(0,5).join('、')||'无')}</div><div>关系：${esc(x.relations.slice(0,5).map(r=>`${r.to}（${r.rel}）`).join('、')||'无')}</div></div>`).join('');pages.push(`<div class="print-page"><div class="print-grid">${cards}</div></div>`)}$('#printArea').innerHTML=pages.join('')}`
function renderEvents(){const types=[...new Set(DATA.events.map(x=>x.type))].sort();const cats=DATA.eventCategories||[];const counts={};DATA.events.forEach(x=>{counts[x.category]=(counts[x.category]||0)+1});const list=DATA.events.filter(x=>(state.eventCategory==='全部类别'||x.category===state.eventCategory)&&(!state.eventQuery||`${x.name} ${x.location} ${x.participants.join(' ')}`.toLowerCase().includes(state.eventQuery.toLowerCase())));const page=slicePage(list,state.eventPage);$('#events').innerHTML=`<div class="section-head"><div><h2>事件索引</h2><p>${metrics.events} 件事件；年份待考的 ${metrics.unknownEvents} 件仍保留在索引中。</p></div></div><div class="panel"><div class="toolbar"><label>类别</label><select id="eventCategory">${cats.map(c=>`<option ${state.eventCategory===c?'selected':''}>${esc(c)}（${counts[c]||0}）</option>`).join('')}</select><input class="search grow" id="eventQuery" value="${esc(state.eventQuery)}" placeholder="搜索事件、地点或参与者"></div><div class="table-wrap"><table class="data-table"><thead><tr><th>事件</th><th>年份</th><th>类别</th><th>原类型</th><th>地点</th><th>参与者</th><th>来源</th></tr></thead><tbody>${page.map(x=>`<tr><td><button class="link-button" data-event-id="${x.id}">${esc(x.name)}</button></td><td>${esc(x.year||'待考')}</td><td>${catBadge(x.category,eventCatColor(x.category))}</td><td class="muted">${esc(x.type)}</td><td>${esc(x.location)}</td><td>${esc(x.participants.slice(0,5).join('、'))}${x.participants.length>5?' …':''}</td><td>${x.sources.length}章</td></tr>`).join('')||'<tr><td colspan="7" class="empty">没有匹配事件</td></tr>'}</tbody></table></div>${pager(state.eventPage,list.length)}</div>`;$('#eventCategory').addEventListener('change',e=>{state.eventCategory=e.target.value;state.eventPage=1;renderEvents()});$('#eventQuery').addEventListener('input',e=>{state.eventQuery=e.target.value;state.eventPage=1;renderEvents()});const root=$('#events');bindPaging(root,delta=>{state.eventPage+=delta;renderEvents()});root.querySelectorAll('[data-event-id]').forEach(b=>b.addEventListener('click',()=>showEvent(DATA.events.find(x=>x.id===b.dataset.eventId))))}
function renderRelations(){const cats=DATA.relationCategories||[];const list=DATA.relations.filter(x=>(state.relationCategory==='全部类别'||x.category===state.relationCategory)&&(!state.relationQuery||`${x.from} ${x.to} ${x.rel} ${x.sourceTitle}`.toLowerCase().includes(state.relationQuery.toLowerCase())));const page=slicePage(list,state.relationPage);const counts={};DATA.relations.forEach(x=>{counts[x.category]=(counts[x.category]||0)+1});$('#relations').innerHTML=`<div class="section-head"><div><h2>关系索引</h2><p>${metrics.relations} 条关系完整保留；自由文本关系已归入 ${cats.length} 个类别，原文仍可查。</p></div></div><div class="panel"><div class="toolbar"><label>类别</label><select id="relationCategory">${cats.map(c=>`<option ${state.relationCategory===c?'selected':''}>${esc(c)}</option>`).join('')}</select><span class="muted">当前类别 ${counts[state.relationCategory]||metrics.relations} 条</span><input class="search grow" id="relationQuery" value="${esc(state.relationQuery)}" placeholder="人物、关系或来源章节"></div><div class="table-wrap"><table class="data-table"><thead><tr><th>主体</th><th>类别</th><th>关系</th><th>对象</th><th>来源</th></tr></thead><tbody>${page.map(x=>`<tr><td>${esc(x.from)}</td><td>${catBadge(x.category,relCatColor(x.category))}</td><td>${esc(x.rel)}</td><td>${esc(x.to)}</td><td>${esc(x.sourceTitle)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">没有匹配关系</td></tr>'}</tbody></table></div>${pager(state.relationPage,list.length)}</div>`;$('#relationCategory').addEventListener('change',e=>{state.relationCategory=e.target.value;state.relationPage=1;renderRelations()});$('#relationQuery').addEventListener('input',e=>{state.relationQuery=e.target.value;state.relationPage=1;renderRelations()});const root=$('#relations');bindPaging(root,delta=>{state.relationPage+=delta;renderRelations()})}
const HAN_NUM=['','一','二','三','四','五','六','七','八','九'];
const hanNum=n=>{n=Math.round(n);if(n<=0)return String(n);if(n<=10)return HAN_NUM[n];if(n<20)return '十'+(n%10?HAN_NUM[n%10]:'');const t=Math.floor(n/10),u=n%10;return HAN_NUM[t]+'十'+(u?HAN_NUM[u]:'')};
const reignOf=year=>{const y=Number(year);if(!y)return null;return (DATA.reigns||[]).find(r=>y>=r.start&&y<=r.end)||null};
const eraTag=year=>{const y=parseInt(year,10);if(!y)return '';const r=reignOf(y);if(!r)return '';return `<span class="era-tag">${esc(r.era)}${hanNum(y-r.start+1)}年</span>`};
const reignColor=(i)=>`hsl(${(i*137)%360},38%,${i%2?46:38}%)`;
function renderDynasty(){const reigns=DATA.reigns||[];if(!reigns.length){$('#dynasty').innerHTML='<div class="empty">暂无帝王数据</div>';return}
const minY=1368,maxY=1644,span=maxY-minY+1;
const counts=reigns.map(r=>DATA.timeline.filter(e=>e.year_start>=r.start&&e.year_start<=r.end).length);
const perYear={};DATA.timeline.forEach(e=>{const y=e.year_start;if(y>=minY&&y<=maxY)perYear[y]=(perYear[y]||0)+1});
const maxPerYear=Math.max(...Object.values(perYear),1);
let bars='';for(let y=minY;y<=maxY;y++){const c=perYear[y]||0;const r=reignOf(y);bars+=`<span style="height:${c?Math.max(10,c*100/maxPerYear):3}%;background:${r?reignColor(r.order-1):'#c9bfae'}" title="${y}年${r?' · '+esc(r.era):''} · 事件 ${c} 件"></span>`}
const segs=reigns.map((r,i)=>`<div class="dynasty-seg" data-era="${esc(r.era)}" style="width:${(r.end-r.start+1)*100/span}%;background:${reignColor(i)}" title="${esc(r.era)}（${esc(r.name)} ${esc(r.temple)}）${r.start}-${r.end} · 本朝事件 ${counts[i]} 件"><b>${esc(r.era)}</b></div>`).join('');
const sel=state.dynastyEra||'';
const cards=reigns.map((r,i)=>`<div class="dynasty-card ${sel===r.era?'active':''}" data-era="${esc(r.era)}" style="--cat:${reignColor(i)}"><h3>${esc(r.era)}</h3><div class="muted">${esc(r.name)} · ${esc(r.temple)} · ${r.start}-${r.end} · 在位${r.end-r.start+1}年</div><p>${esc(r.note)}</p><span class="tag" style="margin-top:8px">${counts[i]} 件大事</span></div>`).join('');
let detail='';
if(sel){const idx=reigns.findIndex(r=>r.era===sel);if(idx>=0){const r=reigns[idx];
const evs=DATA.timeline.filter(e=>e.year_start>=r.start&&e.year_start<=r.end).sort((a,b)=>a.year_start-b.year_start);
const persons={};evs.forEach(e=>(e.participants||[]).forEach(p=>persons[p]=(persons[p]||0)+1));
const topP=Object.entries(persons).sort((a,b)=>b[1]-a[1]).slice(0,12);
detail=`<div class="panel" style="margin-top:14px"><div class="section-head"><div><h2 style="font-size:18px">${esc(r.era)}一朝 · ${esc(r.name)}（${esc(r.temple)}）</h2><p>${r.start}-${r.end} · 在位 ${r.end-r.start+1} 年 · ${esc(r.note)}</p></div><span class="muted">再次点击同一卡片可收起</span></div><div class="dynasty-detail-grid"><div><h3 style="margin:0 0 8px;font-size:14px">本朝大事（${evs.length}）</h3>${evs.slice(0,14).map(e=>`<div class="dynasty-event-row"><span><span class="cat-dot" style="--cat:${eventCatColor(e.category)}"></span><button class="link-button" data-event-id="${e.id}">${esc(e.name)}</button></span><span class="muted">${esc(e.year||'')} · ${esc((e.participants||[]).slice(0,3).join('、'))}</span></div>`).join('')||'<div class="empty">本朝暂无可纪年大事</div>'}</div><div><h3 style="margin:0 0 8px;font-size:14px">本朝活跃人物</h3><div class="source-row">${topP.map(([p,c])=>`<span class="source-chip">${esc(p)} · ${c} 件</span>`).join('')||'<span class="muted">暂无</span>'}</div></div></div></div>`}}
$('#dynasty').innerHTML=`<div class="section-head"><div><h2>帝王谱系</h2><p>十六位天子、十七段年号；${DATA.timeline.length} 件可纪年大事按在位期自动归位，条带宽度即在位时长。</p></div><span class="status">帝系为人工整理 · 事件自动对位</span></div><div class="panel" style="margin-bottom:14px"><div class="section-head"><div><h2 style="font-size:16px">一、在位条带与逐年大事热度</h2><p>上条为年号区间（1368-1644），下条为逐年事件数，颜色随年号切换；悬停看具体年份。</p></div></div><div class="dynasty-band">${segs}</div><div class="dynasty-hist">${bars}</div><div class="dynasty-scale"><span>1368 · 洪武开国</span><span>1644 · 崇祯殉国</span></div></div><div class="panel"><div class="section-head"><div><h2 style="font-size:16px">二、十六帝小传</h2><p>点击任一帝王卡片或上方年号条，展开本朝大事与活跃人物。</p></div></div><div class="dynasty-cards">${cards}</div></div>${detail}`;
document.querySelectorAll('#dynasty .dynasty-card,#dynasty .dynasty-seg').forEach(el=>el.addEventListener('click',()=>{state.dynastyEra=state.dynastyEra===el.dataset.era?'':el.dataset.era;renderDynasty()}));
document.querySelectorAll('#dynasty [data-event-id]').forEach(b=>b.addEventListener('click',()=>showEvent(DATA.events.find(x=>x.id===b.dataset.eventId))))}
function renderChronicle(){const lives=(DATA.lifespans||[]).slice();if(!lives.length){$('#chronicle').innerHTML='<div class="empty">暂无年谱数据</div>';return}const GROUP_COLORS={'帝系':'#8d3025','开国功臣':'#b88b35','永乐群英':'#476b86','内阁文臣':'#527b5c','武将勋臣':'#8c6344','宦官佞幸':'#706b91','对手与民变':'#a24b55','文苑行者':'#6f6a63'};const minY=Math.min(...lives.map(x=>x.birth))-3,maxY=Math.max(...lives.map(x=>x.death))+3,span=maxY-minY;const pct=y=>(y-minY)*100/span;const reigns=DATA.reigns||[];let bands='';if(1368>minY)bands+=`<span class="chronicle-band" style="left:0;width:${pct(Math.min(1368,maxY))}%;background:#9d9a8d" title="明兴之前"></span>`;reigns.forEach(r=>{bands+=`<span class="chronicle-band" style="left:${pct(r.start)}%;width:${(r.end-r.start+1)*100/span}%;background:${reignColor(r.order-1)}" title="${esc(r.era)} ${r.start}-${r.end}"></span>`});if(maxY>1644)bands+=`<span class="chronicle-band" style="left:${pct(1645)}%;width:${pct(maxY)-pct(1645)}%;background:#9d9a8d" title="甲申之后"></span>`;let ticks='';for(let y=Math.ceil(minY/25)*25;y<=maxY;y+=25){ticks+=`<span class="chronicle-tick" style="left:${pct(y)}%">${y}</span>`}const groups=[];lives.slice().sort((a,b)=>a.birth-b.birth).forEach(l=>{let g=groups.find(x=>x.label===l.group);if(!g){g={label:l.group,items:[]};groups.push(g)}g.items.push(l)});const charSet=new Set(DATA.characters.map(c=>c.name));const rows=groups.map(g=>{const c=GROUP_COLORS[g.label]||'#9d9a8d';return `<div class="chronicle-group"><span class="cat-dot" style="--cat:${c}"></span>${esc(g.label)} · ${g.items.length} 人</div>`+g.items.map(l=>{const left=pct(l.birth),w=Math.max(.7,pct(l.death+1)-left);const btn=charSet.has(l.name)?`<button class="link-button" data-person="${esc(l.name)}">${esc(l.name)}</button>`:esc(l.name);return `<div class="chronicle-row"><div class="chronicle-name">${btn}</div><div class="chronicle-track"><span class="chronicle-bar" style="left:${left}%;width:${w}%;background:${c}" title="${esc(l.name)} · ${l.birth}–${l.death}${l.note?' · '+esc(l.note):''}"></span></div></div>`}).join('')}).join('');$('#chronicle').innerHTML=`<div class="section-head"><div><h2>年谱 · 人物生平对照</h2><p>${lives.length} 位主要人物的生卒年横向展开，底色条带为十六帝在位期，人物与年号直接对位；点击人名打开详情。</p></div><span class="status draft">生卒年据通行史料整理 · 需史料核验</span></div><div class="panel"><div class="chronicle-wrap">${bands}<div class="chronicle-content"><div class="chronicle-axis">${ticks}</div>${rows}</div></div></div>`;document.querySelectorAll('#chronicle [data-person]').forEach(b=>b.addEventListener('click',()=>{const x=DATA.characters.find(y=>y.name===b.dataset.person);if(!x)return;openDetail(x.name,`<div class="detail-grid"><div class="detail-block"><strong>身份</strong><p>${esc(x.role)}</p></div><div class="detail-block"><strong>势力</strong><p>${esc(x.faction||'未标注')}</p></div><div class="detail-block"><strong>生卒 / 籍贯</strong><p>${esc(x.life)} · ${esc(x.birth)}</p></div><div class="detail-block"><strong>状态</strong><p>${esc(x.status)}</p></div><div class="detail-block detail-wide"><strong>别名</strong><p>${esc(x.aliases.join('、')||'无')}</p></div><div class="detail-block detail-wide"><strong>涉及事件（${x.events.length}）</strong>${x.events.length?`<ul class="event-list">${x.events.slice(0,12).map(n=>`<li><button class="link-button" data-event-name="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul>`:`<p class="muted">书中未作为事件参与者出现。</p>`}</div><div class="detail-block detail-wide"><strong>同章上下文事件（${x.contextEvents.length}）</strong>${x.contextEvents.length?`<ul class="event-list">${x.contextEvents.slice(0,15).map(n=>`<li><button class="link-button" data-event-name="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul><p class="muted">书中同章提及，非本人物直接参与（可作关联线索）</p>`:`<p class="muted">同章亦无其它事件记录。</p>`}</div><div class="detail-block detail-wide"><strong>来源章节</strong><div class="source-row">${chapterChips(x.chapters.map(k=>({key:k,...DATA.chapters[k]})))}</div></div></div>`);bindEventNameClicks()}))}function renderTimeline(){const cats=DATA.eventCategories||[];const filtered=(state.timelineCategory==='全部类别')?DATA.timeline:DATA.timeline.filter(x=>x.category===state.timelineCategory);const page=slicePage(filtered,state.timelinePage);const groups=[];for(const event of page){const year=event.year||'年份待考';let group=groups.find(x=>x.year===year);if(!group){group={year,items:[]};groups.push(group)}group.items.push(event)}$('#timeline').innerHTML=`<div class="section-head"><div><h2>时间轴</h2><p>按数值年份排序；年份待考事件单独保留，不再混入历史顺序。</p></div></div><div class="panel"><div class="toolbar"><label>类别</label><select id="timelineCategory">${cats.map(c=>`<option ${state.timelineCategory===c?'selected':''}>${esc(c)}</option>`).join('')}</select><span class="muted">圆点颜色即事件类别</span></div><div class="timeline">${groups.map(g=>`<div class="year-group"><h3>${esc(g.year)}${eraTag(g.year)}</h3>${g.items.map(x=>`<div class="timeline-item"><span class="cat-dot" style="--cat:${eventCatColor(x.category)}" title="${esc(x.category)}"></span><button data-event-id="${x.id}">${esc(x.name)}</button><span class="muted"> · ${esc(x.participants.slice(0,4).join('、'))}</span></div>`).join('')}</div>`).join('')}</div>${pager(state.timelinePage,filtered.length)}</div><div class="panel unknown"><div class="section-head"><div><h2 style="font-size:18px">年份待考</h2><p>${DATA.unknownTimeline.length} 件事件仍在事件索引中。</p></div></div><div class="source-row">${DATA.unknownTimeline.slice(0,80).map(x=>`<button class="source-chip link-button" data-event-id="${x.id}">${esc(x.name)}</button>`).join('')}</div></div>`;$('#timelineCategory').addEventListener('change',e=>{state.timelineCategory=e.target.value;state.timelinePage=1;renderTimeline()});const root=$('#timeline');bindPaging(root,delta=>{state.timelinePage+=delta;renderTimeline()});root.querySelectorAll('[data-event-id]').forEach(b=>b.addEventListener('click',()=>showEvent(DATA.events.find(x=>x.id===b.dataset.eventId))))}
renderOverview();state.rendered.overview=true;
</script>
</body></html>'''


def render(scope: str, output: Path):
    payload = build_scope(scope)
    document = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
    document = document.replace("__TITLE__", payload["scopeLabel"])
    # Normalize the compact inline template before publishing.
    document = document.replace("pages.join('')}`", "pages.join('')}")
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
