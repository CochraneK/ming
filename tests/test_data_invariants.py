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
