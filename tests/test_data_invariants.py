# -*- coding: utf-8 -*-
"""数据不变量测试：直接跑 validators 并补充若干业务口径断言。

依赖 data/data.json 与 data/extract_raw.json（二者均可公开），
**不依赖 data/chapters.json**（含原书全文，不入库），因此在 CI 也能跑。
"""

from __future__ import annotations

import _support

import validators as V


def test_no_validator_errors():
    """ERROR 级校验必须全清——它代表数据自相矛盾，出现即不可发布。"""
    findings = V.validate_payload(_support.payload("full"))
    errors = [f for f in findings if f.severity == V.ERROR]
    assert not errors, "\n".join("%s %s" % (f.rule, f.message) for f in errors)


def test_expected_scale():
    """规模锚点：数字大幅漂移说明上游抽取/合并出问题，需要人工确认。"""
    m = _support.payload("full")["metrics"]
    assert m["chapters"] == 156
    assert m["characters"] == 1231
    assert m["relations"] == 2324
    assert m["events"] == 1106
    assert m["locations"] >= 561, "地点数不应少于 data.json 的 561（event_places 注入只增不减）"


def test_unknown_year_events_are_declared():
    """未知年份事件必须同时出现在 metrics 与 unknownTimeline，口径一致。"""
    payload = _support.payload("full")
    unknown = payload["unknownTimeline"]
    assert len(unknown) == payload["metrics"]["unknownEvents"]
    assert all(e.get("year_start") is None for e in unknown)
    assert all(e.get("year_start") is not None for e in payload["timeline"])


def test_graph_scheme_a_only_persons():
    """方案 A：关系图节点只能是人物表内实体。"""
    payload = _support.payload("full")
    graph = payload["relationGraphFull"]
    names = {c["name"] for c in payload["characters"]}
    node_names = {n["name"] for n in graph["nodes"]}
    assert node_names <= names
    assert len(node_names) == graph["stats"]["nodes"]
    assert graph["stats"]["excludedNonPerson"] > 0, "应当确实排除掉一些非人物端点关系"


def test_graph_excluded_nonperson_matches_relation_kinds():
    """「排除多少条含非人物端点的关系」只允许有一个口径。

    R-GRAPH-00 用 stats.excludedNonPerson，审计 R-REL-00 用 endpointKind 现算，
    两者曾经漂移（审计那侧是个恒为 0 的死表达式），这里钉死它们必须相等。
    """
    payload = _support.payload("full")
    stats = payload["relationGraphFull"]["stats"]
    bad = 0
    for r in payload["relations"]:
        k = r.get("endpointKind") or {}
        if (k.get("from") or "person") != "person" or (k.get("to") or "person") != "person":
            bad += 1
    assert bad == stats["excludedNonPerson"], \
        "现算 %d 条 vs stats %d 条" % (bad, stats["excludedNonPerson"])


def test_graph_isolated_arithmetic():
    """connected + isolated == persons（曾经把孤立人数算错的回归点）。"""
    stats = _support.payload("full")["relationGraphFull"]["stats"]
    assert stats["connected"] == stats["nodes"]
    assert stats["connected"] + stats["isolated"] == stats["persons"]


def test_partial_scope_uses_induced_relations():
    """分部报告的关系统计必须用诱导子图（两端都在本范围内），否则边数会虚高。

    注意：判定依据是**关系两端的人物**是否在本范围，而不是关系自身的出处章节——
    「世交」「推导」这类关系的 source 不是章节号（如 curated / 推导），
    所以不能拿 `rel["source"] in chapters` 当判据。
    """
    full = _support.payload("full")
    p1 = _support.payload("p1")
    assert p1["relationScope"] == "induced"
    assert full["relationScope"] == "all"

    names = {c["name"] for c in p1["characters"]}
    for rel in p1["relations"]:
        assert rel["from"] in names and rel["to"] in names, "%s：%s→%s 越界" % (rel["id"], rel["from"], rel["to"])

    full_by_id = {r["id"] for r in full["relations"]}
    p1_ids = {r["id"] for r in p1["relations"]}
    assert p1_ids <= full_by_id, "分部关系必须是全书关系的子集"
    assert len(p1_ids) < len(full_by_id), "诱导子图应显著小于全书"


def test_alias_index_resolves_common_names():
    """别名搜索的关键路径：常见别名必须能落到规范名。"""
    payload = _support.payload("full")
    alias = payload["aliasIndex"]
    for raw, expect in (
        ("崇祯", "朱由检"),
        ("崇祯帝", "朱由检"),
        ("道衍", "姚广孝"),
        ("王阳明", "王守仁"),
        ("朱重八", "朱元璋"),
    ):
        assert alias.get(raw) == expect, "%s → %r" % (raw, alias.get(raw))
    assert "鎏金" not in alias, "不存在的别名不得凭空出现在索引里"


def test_build_is_deterministic():
    """同一份数据重跑必须得到同一份 payload（力导向已挪到浏览器，Python 端无随机）。"""
    a = _support.payload("full")
    b = _support.fresh_payload("full")
    assert a["metrics"] == b["metrics"]
    assert a["relationGraphFull"]["stats"] == b["relationGraphFull"]["stats"]
    assert [n["x"] for n in a["relationGraphFull"]["nodes"]] == [n["x"] for n in b["relationGraphFull"]["nodes"]]
    assert a["aliasIndex"] == b["aliasIndex"]


def test_relation_ids_stable_across_scopes():
    """关系 id 是内容哈希，跨范围构建也必须一致（deep link 依赖它）。"""
    full = {r["id"] for r in _support.payload("full")["relations"]}
    p1 = {r["id"] for r in _support.payload("p1")["relations"]}
    assert p1 <= full, "分部关系 id 应是全书关系 id 的子集"


def test_every_character_has_profile():
    """P2-03：前端卡面已改为只读 profile，缺一个都会退化成空卡，必须全员覆盖。"""
    payload = _support.payload("full")
    keys = {"raw", "label", "regime", "dynasty", "period", "factions", "orgs",
            "categories", "office", "origin", "jinshi_year", "note"}
    for c in payload["characters"]:
        p = c.get("profile")
        assert isinstance(p, dict), "%s 缺 profile" % c["name"]
        assert set(p) == keys, "%s 的 profile 字段集漂移" % c["name"]
        assert p["raw"] == (c.get("factionRaw") or ""), "%s 的原串无法回查" % c["name"]
        assert p["label"], "%s 的 profile.label 为空" % c["name"]


def test_entity_graph_superset_of_person_graph():
    """Phase 6 双模式图的口径契约：

    - 人物图（方案 A）只含人物↔人物关系；
    - 实体图含全部关系端点（人物/地点/机构/政权/其他）；
    - 人物图的节点与边必须是实体图的子集——否则两张图互相打架。
    """
    payload = _support.payload("full")
    person = payload["relationGraphFull"]
    entity = payload["relationGraphEntities"]

    p_names = {n["name"] for n in person["nodes"]}
    e_names = {n["name"] for n in entity["nodes"]}
    assert p_names <= e_names, "人物图节点必须是实体图节点的子集"

    def undirected(g):
        return {tuple(sorted((l["source"], l["target"]))) for l in g["links"]}

    p_edges, e_edges = undirected(person), undirected(entity)
    assert p_edges <= e_edges, "人物图的边必须都在实体图里"
    assert len(p_edges) < len(e_edges), "实体图应当比人物图多出非人物关系"


def test_entity_graph_stats_internally_consistent():
    """实体图统计必须自洽，且绝不能把「实体数」说成「人物数」。"""
    payload = _support.payload("full")
    entity = payload["relationGraphEntities"]
    stats = entity["stats"]

    assert stats["nodes"] == len(entity["nodes"])
    assert stats["edges"] == len(entity["links"])
    assert stats["personNodes"] + stats["nonPersonNodes"] == stats["nodes"]
    assert sum(stats["byKind"].values()) == stats["nodes"]
    assert stats["personNodes"] == stats["bookPersons"] - stats["isolatedPersons"]

    # 节点类型只能是约定内的 5 种；标成 person 的必须真在人物表内
    names = {c["name"] for c in payload["characters"]}
    for node in entity["nodes"]:
        assert node["kind"] in {"person", "place", "org", "regime", "other"}, node
        if node["kind"] == "person":
            assert node["name"] in names, "%s 标成人物却不在人物表内" % node["name"]

    # 端点必须落在节点集合内（不允许悬空引用）
    node_names = {n["name"] for n in entity["nodes"]}
    for link in entity["links"]:
        assert link["source"] in node_names and link["target"] in node_names


def test_entity_graph_is_deterministic():
    """实体图布局同样必须纯确定性（重跑不得漂移，否则 deep link / 截图对不上）。"""
    a = _support.payload("full")["relationGraphEntities"]
    b = _support.fresh_payload("full")["relationGraphEntities"]
    assert a["stats"] == b["stats"]
    assert [(n["name"], n["x"], n["y"]) for n in a["nodes"]] == \
           [(n["name"], n["x"], n["y"]) for n in b["nodes"]]


def test_insight_index_is_symmetric():
    """洞察联动索引：正向（每节命中哪些实体）与反向（实体被哪几节提到）必须互为逆表。

    一旦漂移，前端要么漏链（反向查不到章节），要么链到空白（正向没有对应表面形式）。
    同时校验通称黑名单没有泄漏——否则正文里每个「宦官」都会被链成某个人物卡。
    """
    from core.insight_link import GENERIC_BLOCK

    ix = _support.payload("full").get("insightIndex") or {}
    assert ix, "payload 缺少 insightIndex（构建期未接入？）"
    sections = ix.get("sections") or {}
    alias = ix.get("alias") or {}
    by_person = ix.get("byPerson") or {}
    assert len(sections) >= 15, "索引到的章节数异常少：%d" % len(sections)
    assert len(by_person) >= 50, "反向索引到的人物数异常少：%d" % len(by_person)

    for sid, hits in sections.items():
        for surface in hits.get("p", []):
            canonical = alias.get(surface, surface)
            assert sid in (by_person.get(canonical) or []),                 "正向有 %s/%s，反向 byPerson 却查不到该节" % (sid, surface)
            assert surface not in GENERIC_BLOCK, "通称 %r 泄漏进人物联动" % surface

    for canonical, sids in by_person.items():
        for sid in sids:
            surfaces = (sections.get(sid) or {}).get("p") or []
            assert any(alias.get(s, s) == canonical for s in surfaces),                 "反向 %s→%s，正向该节却查不到这个人的任何表面形式" % (canonical, sid)


def test_insight_place_event_index_is_symmetric():
    """地点/事件联动索引同样必须正反映射互逆。

    原测试只守了 byPerson，地点与事件的反向索引一旦漂移，
    地点卡/事件卡上的「相关洞察」就会整块消失或指向不存在的章节。
    """
    payload = _support.payload("full")
    ix = payload.get("insightIndex") or {}
    assert ix, "payload 缺少 insightIndex"
    sections = ix.get("sections") or {}
    place_alias = ix.get("placeAlias") or {}

    for kind, key, rev, ali in (("l", "l", "byPlace", place_alias),
                                ("e", "e", "byEvent", {})):
        by = ix.get(rev) or {}
        for sid, hits in sections.items():
            for surface in hits.get(key, []):
                canonical = ali.get(surface, surface)
                assert sid in (by.get(canonical) or []),                     "正向有 %s/%s，反向 %s 却查不到该节" % (sid, surface, rev)
        for canonical, sids in by.items():
            for sid in sids:
                surfaces = (sections.get(sid) or {}).get(key) or []
                assert any(ali.get(s, s) == canonical for s in surfaces),                     "反向 %s→%s，正向该节却查不到该%s的任何表面形式" % (canonical, sid, kind)

    # 反向索引的键必须都是实体表里的规范名，否则详情永远查不到
    loc_names = {x.get("ancient") for x in payload.get("locations", [])}
    ev_names = {x.get("name") for x in payload.get("events", [])}
    for k in ix.get("byPlace", {}):
        assert k in loc_names, "byPlace 键 %r 不是地点规范名" % k
    for k in ix.get("byEvent", {}):
        assert k in ev_names, "byEvent 键 %r 不是事件名称" % k


def test_insight_alias_targets_canonical():
    """alias / placeAlias 的值必须是规范名——前端拿它当 data-ins-* 直接查人物/地点表。

    值若是别名或通称，点击后 showPerson/showLocation 会静默 return false，
    表现为「链接点了没反应」。
    """
    payload = _support.payload("full")
    ix = payload.get("insightIndex") or {}
    char_names = {x.get("name") for x in payload.get("characters", [])}
    loc_names = {x.get("ancient") for x in payload.get("locations", [])}

    for surface, canonical in (ix.get("alias") or {}).items():
        assert canonical in char_names, "alias %r→%r 不是人物规范名" % (surface, canonical)
    for surface, canonical in (ix.get("placeAlias") or {}).items():
        assert canonical in loc_names, "placeAlias %r→%r 不是地点规范名" % (surface, canonical)


def _geo_annotations():
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "data" / "geo_annotations.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_geo_annotations_no_stale_placeholders():
    """同一地名不能既已有坐标条目、又留着「抽取待补」的占位条目。

    占位条目没有 lat/lng，审计里 float(缺省 0) 会把它算成 (0,0)，
    与真坐标凑成「两个候选坐标」→ 同名异地误报，把真冲突淹没在噪声里。
    """
    by = {}
    for g in _geo_annotations():
        by.setdefault(g.get("ancient"), []).append(g)
    bad = []
    for name, items in by.items():
        located = [x for x in items if x.get("lat") is not None and x.get("lng") is not None]
        if located and len(located) != len(items):
            bad.append(name)
    assert not bad, "这些地名同时有坐标条目与占位条目（应删占位）：%s" % "、".join(sorted(bad))


def test_geo_annotations_no_coord_conflict():
    """同一地名在标注表里不允许出现两套不同坐标——那意味着还有同名异地没拆。"""
    by = {}
    for g in _geo_annotations():
        if g.get("lat") is None or g.get("lng") is None:
            continue
        by.setdefault(g.get("ancient"), set()).add(
            (round(float(g["lat"]), 2), round(float(g["lng"]), 2)))
    bad = sorted(n for n, s in by.items() if len(s) > 1)
    assert not bad, "同名异地未拆分：%s" % "、".join(bad)


def test_place_mentions_partition_is_lossless():
    """altNames / mentionContext 只能是 mentionedAs 的一个划分：不多、不少、不重。

    前端「别称」块只吃 altNames、「书中提及」块只吃 mentionContext，
    两者合起来必须等于原字段——否则要么别称凭空多出来，要么原文提及被吞掉。
    """
    bad = []
    for l in _support.payload("full").get("locations", []):
        raw = list(dict.fromkeys(l.get("mentionedAs") or []))
        alt = l.get("altNames") or []
        ctx = l.get("mentionContext") or []
        if set(alt) & set(ctx) or set(alt) | set(ctx) != set(raw):
            bad.append(l.get("ancient"))
    assert not bad, "mention 划分与原字段不一致：%s" % "、".join(bad[:20])


def test_place_alt_names_are_place_like():
    """altNames 必须都像「另一个叫法」——说明片段（含标点/描述词/人名）不许混进来。

    这是「别称：熊廷弼不守、努尔哈赤退兵错过之关键据点…」那次缺陷的回归闸。
    """
    from core.place_mentions import is_context_fragment

    payload = _support.payload("full")
    known = {l.get("ancient") for l in payload.get("locations", [])}
    known |= {c.get("name") for c in payload.get("characters", [])}
    known |= {e.get("name") for e in payload.get("events", [])}
    bad = []
    for l in payload.get("locations", []):
        for a in l.get("altNames") or []:
            if is_context_fragment(a, l.get("ancient"), known):
                bad.append("%s: %s" % (l.get("ancient"), a))
    assert not bad, "这些串被误判成别称：%s" % "；".join(bad[:15])
