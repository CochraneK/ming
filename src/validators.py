# -*- coding: utf-8 -*-
"""报告 payload 不变量校验：全项目唯一真源。

同一份校验同时被三处使用，避免口径漂移：
- ``python src/build.py --check``  构建前拦截（ERROR 直接非零退出）
- ``tests/test_invariants.py``     单元测试
- ``.github/workflows/ci.yml``     CI 无原书全文（data/chapters.json 不可公开）也能跑

设计约定：
- 每个规则返回 ``Finding``，severity 只有 ERROR / WARNING / INFO 三档；
- **ERROR 代表数据自相矛盾**（计数对不上、引用悬空、ID 重复），必须修；
- **WARNING 代表已知待办**（如 7 件未知年份事件、延安府同名异地），不阻塞发布；
- INFO 只做提示与统计，不进退出码。
"""

from __future__ import annotations

import re
from pathlib import Path

from core.geo import coord_problem, has_coords

ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"

_SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}

REQUIRED_TOP_KEYS = (
    "scope",
    "scopeLabel",
    "model",
    "relationScope",
    "chapters",
    "locations",
    "events",
    "relations",
    "characters",
    "timeline",
    "unknownTimeline",
    "distribution",
    "visualizations",
    "relationGraphFull",
    "aliasIndex",
    "metrics",
    "reigns",
    "lifespans",
)

ENTITY_TYPES = ("person", "place", "org", "regime", "other")
_SCHEMA_VERSION = 2
_EVENT_ID_RE = re.compile(r"^event-\d{4}$")


class Finding:
    """一条校验结论。items 用于承载具体条目，避免刷屏。"""

    __slots__ = ("severity", "rule", "message", "items")

    def __init__(self, severity: str, rule: str, message: str, items=None):
        self.severity = severity
        self.rule = rule
        self.message = message
        self.items = list(items or [])

    def as_dict(self):
        return {
            "severity": self.severity,
            "rule": self.rule,
            "message": self.message,
            "items": self.items,
        }

    def __repr__(self):
        return "<%s %s %s>" % (self.severity, self.rule, self.message)


def _summarize(items, limit=6):
    items = list(items)
    head = "、".join(str(x) for x in items[:limit])
    if len(items) > limit:
        head += " …（共 %d 条）" % len(items)
    return head


def sort_findings(findings):
    return sorted(findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))


def count_by_severity(findings):
    out = {ERROR: 0, WARNING: 0, INFO: 0}
    for f in findings:
        out[f.severity] = out.get(f.severity, 0) + 1
    return out


# --------------------------------------------------------------------------
# 结构 / 计数
# --------------------------------------------------------------------------


def check_structure(payload):
    findings = []
    missing = [k for k in REQUIRED_TOP_KEYS if k not in payload]
    if missing:
        findings.append(
            Finding(ERROR, "V-STRUCT-01", "payload 缺少必需顶层字段：%s" % "、".join(missing), missing)
        )
    model = payload.get("model") or {}
    if model.get("schemaVersion") != _SCHEMA_VERSION:
        findings.append(
            Finding(
                ERROR,
                "V-STRUCT-02",
                "model.schemaVersion 应为 %d，实际 %r" % (_SCHEMA_VERSION, model.get("schemaVersion")),
            )
        )
    if tuple(model.get("entityTypes") or ()) != ENTITY_TYPES:
        findings.append(
            Finding(ERROR, "V-STRUCT-03", "model.entityTypes 与约定不一致：%r" % (model.get("entityTypes"),))
        )
    scope = payload.get("scope")
    expect_scope = "all" if scope == "full" else "induced"
    if payload.get("relationScope") != expect_scope:
        findings.append(
            Finding(
                ERROR,
                "V-STRUCT-04",
                "relationScope 应为 %s（scope=%s），实际 %r"
                % (expect_scope, scope, payload.get("relationScope")),
            )
        )
    return findings


def check_metrics(payload):
    """metrics 是页面顶部与 README 引用的数字，必须与真实列表长度一致。"""
    findings = []
    metrics = payload.get("metrics") or {}
    characters = payload.get("characters") or []
    events = payload.get("events") or []
    relations = payload.get("relations") or []
    locations = payload.get("locations") or []
    timeline = payload.get("timeline") or []
    unknown = payload.get("unknownTimeline") or []

    expected = {
        "characters": len(characters),
        "events": len(events),
        "relations": len(relations),
        "locations": len(locations),
        "timedEvents": len(timeline),
        "unknownEvents": len(unknown),
    }
    drift = {k: (metrics.get(k), v) for k, v in expected.items() if metrics.get(k) != v}
    if drift:
        findings.append(
            Finding(
                ERROR,
                "V-METRICS-01",
                "metrics 与实际条数不一致：%s"
                % "; ".join("%s 记为 %r 实为 %r" % (k, a, b) for k, (a, b) in drift.items()),
                list(drift),
            )
        )
    if len(timeline) + len(unknown) != len(events):
        findings.append(
            Finding(
                ERROR,
                "V-METRICS-02",
                "timeline(%d) + unknownTimeline(%d) != events(%d)" % (len(timeline), len(unknown), len(events)),
            )
        )
    located = payload.get("metrics", {}).get("locatedLocations")
    real_located = sum(1 for loc in locations if has_coords(loc.get("lat"), loc.get("lng")))
    if located != real_located:
        findings.append(
            Finding(
                ERROR,
                "V-METRICS-03",
                "metrics.locatedLocations 记为 %r，按 has_coords 实为 %d" % (located, real_located),
            )
        )
    return findings


# --------------------------------------------------------------------------
# 实体 / 关系
# --------------------------------------------------------------------------


def check_characters(payload):
    findings = []
    characters = payload.get("characters") or []
    seen = {}
    dup = []
    bad_id = []
    for c in characters:
        name = c.get("name")
        cid = c.get("id")
        if not name:
            bad_id.append("<无名>")
            continue
        if cid != "person:%s" % name:
            bad_id.append("%s(id=%r)" % (name, cid))
        if cid in seen:
            dup.append(cid)
        seen[cid] = name
    if bad_id:
        findings.append(
            Finding(ERROR, "V-CHAR-01", "人物 id 缺失或与规范名不符：%s" % _summarize(bad_id), bad_id)
        )
    if dup:
        findings.append(Finding(ERROR, "V-CHAR-02", "人物 id 重复：%s" % _summarize(dup), dup))
    id_index = (payload.get("model") or {}).get("idIndex") or {}
    missing = [c.get("name") for c in characters if c.get("id") not in id_index]
    if missing:
        findings.append(
            Finding(
                ERROR,
                "V-CHAR-03",
                "model.idIndex 未覆盖 %d 位人物：%s" % (len(missing), _summarize(missing)),
                missing,
            )
        )
    if characters:
        no_chapter = [c.get("name") for c in characters if not c.get("chapters")]
        if no_chapter:
            findings.append(
                Finding(
                    WARNING,
                    "V-CHAR-04",
                    "%d 位人物没有任何来源章节：%s" % (len(no_chapter), _summarize(no_chapter)),
                    no_chapter,
                )
            )
    return findings


def check_relations(payload):
    findings = []
    relations = payload.get("relations") or []
    entity_types = set(ENTITY_TYPES)
    seen = {}
    dup = []
    bad_field = []
    bad_type = []
    for r in relations:
        rid = r.get("id")
        if not rid:
            bad_field.append("<无 id>")
            continue
        if rid in seen:
            dup.append(rid)
        seen[rid] = True
        src, tgt = r.get("from"), r.get("to")
        if not src or not tgt:
            bad_field.append("%s(端点缺失)" % rid)
            continue
        for side, sid_key, type_key in (("from", "sourceId", "sourceType"), ("to", "targetId", "targetType")):
            name = r.get(side)
            sid = r.get(sid_key)
            stype = r.get(type_key)
            if not isinstance(sid, str) or not sid.endswith(":%s" % name) or sid[: -(len(name) + 1)] != stype:
                bad_field.append("%s(%s=%r)" % (rid, sid_key, sid))
            if stype not in entity_types:
                bad_type.append("%s(%s=%r)" % (rid, type_key, stype))
    if dup:
        findings.append(Finding(ERROR, "V-REL-01", "关系 id 重复：%s" % _summarize(dup), dup))
    if bad_field:
        findings.append(
            Finding(
                ERROR,
                "V-REL-02",
                "%d 条关系的 id/端点字段不一致（如 sourceId 与 from 不匹配）：%s"
                % (len(bad_field), _summarize(bad_field)),
                bad_field,
            )
        )
    if bad_type:
        findings.append(
            Finding(ERROR, "V-REL-03", "%d 条关系的端点类型越界：%s" % (len(bad_type), _summarize(bad_type)), bad_type)
        )
    no_source = [r.get("id") for r in relations if not r.get("source")]
    if no_source:
        findings.append(
            Finding(
                WARNING,
                "V-REL-04",
                "%d 条关系缺章节出处：%s" % (len(no_source), _summarize(no_source)),
                no_source,
            )
        )
    return findings


def check_graph(payload):
    findings = []
    graph = payload.get("relationGraphFull") or {}
    nodes = graph.get("nodes") or []
    links = graph.get("links") or []
    stats = graph.get("stats") or {}
    char_names = {c.get("name") for c in payload.get("characters") or []}
    node_names = {n.get("name") for n in nodes}

    if stats.get("nodes") != len(nodes):
        findings.append(
            Finding(ERROR, "V-GRAPH-01", "stats.nodes=%r 与 nodes=%d 不符" % (stats.get("nodes"), len(nodes)))
        )
    if stats.get("edges") != len(links):
        findings.append(
            Finding(ERROR, "V-GRAPH-02", "stats.edges=%r 与 links=%d 不符" % (stats.get("edges"), len(links)))
        )
    if stats.get("persons") != len(char_names):
        findings.append(
            Finding(
                ERROR,
                "V-GRAPH-03",
                "stats.persons=%r 与人物表 %d 不符" % (stats.get("persons"), len(char_names)),
            )
        )
    connected = stats.get("connected")
    isolated = stats.get("isolated")
    if isinstance(connected, int) and isinstance(isolated, int) and connected + isolated != stats.get("persons"):
        findings.append(
            Finding(
                ERROR,
                "V-GRAPH-04",
                "connected(%r) + isolated(%r) != persons(%r)" % (connected, isolated, stats.get("persons")),
            )
        )
    if connected is not None and connected != len(nodes):
        findings.append(
            Finding(ERROR, "V-GRAPH-05", "stats.connected=%r 与入图节点 %d 不符" % (connected, len(nodes)))
        )

    ghost = sorted({l.get("source") for l in links} | {l.get("target") for l in links} - node_names)
    ghost = [n for n in ghost if n not in node_names]
    if ghost:
        findings.append(
            Finding(ERROR, "V-GRAPH-06", "关系图存在悬空边端点：%s" % _summarize(ghost), ghost)
        )
    non_person = sorted(node_names - char_names)
    if non_person:
        findings.append(
            Finding(
                ERROR,
                "V-GRAPH-07",
                "关系图混入非人物节点（方案 A 禁止）：%s" % _summarize(non_person),
                non_person,
            )
        )
    deg = {}
    for l in links:
        deg[l.get("source")] = deg.get(l.get("source"), 0) + 1
        deg[l.get("target")] = deg.get(l.get("target"), 0) + 1
    isolated_in_graph = sorted(n for n in node_names if n not in deg)
    if isolated_in_graph:
        findings.append(
            Finding(
                ERROR,
                "V-GRAPH-08",
                "入图节点里有 %d 个度数为 0（应收进 isolated）：%s"
                % (len(isolated_in_graph), _summarize(isolated_in_graph)),
                isolated_in_graph,
            )
        )
    for n in nodes:
        for axis in ("x", "y"):
            if not isinstance(n.get(axis), (int, float)):
                findings.append(Finding(ERROR, "V-GRAPH-09", "节点 %s 缺确定性初始坐标 %s" % (n.get("name"), axis)))
                break
    return findings


# --------------------------------------------------------------------------
# 事件 / 地点 / 年号 / 别名
# --------------------------------------------------------------------------


def check_events(payload):
    findings = []
    events = payload.get("events") or []
    seen = set()
    dup = []
    bad_id = []
    for e in events:
        eid = e.get("id")
        if not _EVENT_ID_RE.match(eid or ""):
            bad_id.append(repr(eid))
        if eid in seen:
            dup.append(eid)
        seen.add(eid)
    if bad_id:
        findings.append(
            Finding(ERROR, "V-EVENT-01", "事件 id 格式异常（应为 event-0001）：%s" % _summarize(bad_id), bad_id)
        )
    if dup:
        findings.append(Finding(ERROR, "V-EVENT-02", "事件 id 重复：%s" % _summarize(dup), dup))

    bad_range = [e.get("id") for e in events if e.get("year_start") is not None and e.get("year_end") is not None and e.get("year_start") > e.get("year_end")]
    if bad_range:
        findings.append(
            Finding(ERROR, "V-EVENT-03", "事件年份区间倒挂：%s" % _summarize(bad_range), bad_range)
        )
    no_loc = [e.get("name") for e in events if not e.get("location")]
    if no_loc:
        findings.append(
            Finding(WARNING, "V-EVENT-04", "%d 件事件无地点：%s" % (len(no_loc), _summarize(no_loc)), no_loc)
        )
    unknown = [e.get("name") for e in events if e.get("year_start") is None]
    if unknown:
        findings.append(
            Finding(
                WARNING,
                "V-EVENT-05",
                "%d 件事件年份待考（页面显示「年份待考」）：%s" % (len(unknown), _summarize(unknown)),
                unknown,
            )
        )
    return findings


def check_locations(payload):
    findings = []
    locations = payload.get("locations") or []
    bad_coord = []
    half = []
    for loc in locations:
        lat, lng = loc.get("lat"), loc.get("lng")
        if lat is None and lng is None:
            continue
        if lat is None or lng is None:
            half.append("%s(lat=%r,lng=%r)" % (loc.get("ancient") or loc.get("modern"), lat, lng))
            continue
        problem = coord_problem(lat, lng)
        if problem:
            bad_coord.append("%s：%s" % (loc.get("ancient") or loc.get("modern"), problem))
    if half:
        findings.append(
            Finding(ERROR, "V-GEO-01", "%d 个地点只给了一半坐标：%s" % (len(half), _summarize(half)), half)
        )
    if bad_coord:
        findings.append(
            Finding(ERROR, "V-GEO-02", "%d 个地点坐标非法：%s" % (len(bad_coord), _summarize(bad_coord)), bad_coord)
        )
    no_entity = [loc.get("ancient") for loc in locations if not loc.get("entityId")]
    if no_entity:
        findings.append(
            Finding(ERROR, "V-GEO-03", "%d 个地点缺 entityId：%s" % (len(no_entity), _summarize(no_entity)), no_entity)
        )
    return findings


def check_alias_index(payload):
    findings = []
    alias_index = payload.get("aliasIndex") or {}
    char_names = {c.get("name") for c in payload.get("characters") or []}
    ghost = sorted({v for v in alias_index.values()} - char_names)
    if ghost:
        findings.append(
            Finding(ERROR, "V-ALIAS-01", "别名索引指向不存在的人物：%s" % _summarize(ghost), ghost)
        )
    collide = sorted(k for k in alias_index if k in char_names)
    if collide:
        findings.append(
            Finding(ERROR, "V-ALIAS-02", "别名与某人物规范名撞名（会导致搜索指向错误）：%s" % _summarize(collide), collide)
        )
    findings.append(Finding(INFO, "V-ALIAS-03", "别名索引 %d 条" % len(alias_index)))
    return findings


def check_quotes(payload):
    findings = []
    quotes = payload.get("quotes") or {}
    char_names = {c.get("name") for c in payload.get("characters") or []}
    ghost = sorted(k for k in quotes if k not in char_names)
    if ghost:
        findings.append(
            Finding(WARNING, "V-QUOTE-01", "书内语录挂在不存在的规范名上：%s" % _summarize(ghost), ghost)
        )
    findings.append(Finding(INFO, "V-QUOTE-02", "书内语录覆盖 %d 人" % len(quotes)))
    return findings


def check_reigns(payload):
    findings = []
    reigns = payload.get("reigns") or []
    overlap = []
    ordered = sorted(reigns, key=lambda r: r.get("start") or 0)
    for prev, cur in zip(ordered, ordered[1:]):
        if (prev.get("end") or 0) >= (cur.get("start") or 0):
            overlap.append("%s/%s" % (prev.get("era"), cur.get("era")))
    if overlap:
        findings.append(
            Finding(
                INFO,
                "V-REIGN-01",
                "年号区间重叠 %d 处（多为史实：夺门之变、驾崩同年改元）：%s"
                % (len(overlap), _summarize(overlap)),
                overlap,
            )
        )
    return findings


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

ALL_CHECKS = (
    check_structure,
    check_metrics,
    check_characters,
    check_relations,
    check_graph,
    check_events,
    check_locations,
    check_alias_index,
    check_quotes,
    check_reigns,
)


def validate_payload(payload):
    findings = []
    for fn in ALL_CHECKS:
        findings.extend(fn(payload))
    return sort_findings(findings)


def has_errors(findings):
    return any(f.severity == ERROR for f in findings)


def format_report(findings, total_scope: str = ""):
    counts = count_by_severity(findings)
    lines = []
    if total_scope:
        lines.append("校验范围：%s" % total_scope)
    lines.append(
        "结论：ERROR %d / WARNING %d / INFO %d"
        % (counts.get(ERROR, 0), counts.get(WARNING, 0), counts.get(INFO, 0))
    )
    for f in findings:
        if f.severity == INFO and not f.items:
            lines.append("  [%s] %s %s" % (f.severity, f.rule, f.message))
            continue
        lines.append("  [%s] %s %s" % (f.severity, f.rule, f.message))
        if f.items:
            lines.append("        · %s" % _summarize(f.items, limit=12))
    return "\n".join(lines)


def write_json(findings, path: Path):
    import json

    path.write_text(
        json.dumps([f.as_dict() for f in findings], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
