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
