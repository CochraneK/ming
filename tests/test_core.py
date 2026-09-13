# -*- coding: utf-8 -*-
"""共享核心的单元测试：年份解析、经纬度校验、实体 ID、派系识别。

这些用例不依赖 data/，可单独跑，也用于在数据缺失（如 CI 无原书全文）时
保证核心逻辑本身没退化。
"""

from __future__ import annotations

import _support  # noqa: F401  确保 sys.path 已注入

from core.geo import coord_problem, has_coords, is_valid_lat, is_valid_lng
from core.year_parser import has_numeric_year, year_bounds


def test_year_bounds_empty():
    assert year_bounds(None) == (None, None)
    assert year_bounds("") == (None, None)
    assert has_numeric_year("") is False


def test_year_bounds_single_year():
    assert year_bounds(1368) == (1368, 1368)
    assert year_bounds("1402") == (1402, 1402)
    assert year_bounds("1402年") == (1402, 1402)


def test_year_bounds_range():
    assert year_bounds("1368-1398") == (1368, 1398)
    assert year_bounds("1368至1398") == (1368, 1398)
    assert year_bounds("1405—1433") == (1405, 1433)


def test_year_bounds_reign_text_is_unknown():
    # 「万历末年」这类必须判定为未知年份，否则审计与报告口径会打架
    for text in ("万历末年", "洪武年间", "永乐初", "约嘉靖中期"):
        assert year_bounds(text) == (None, None), text
        assert has_numeric_year(text) is False, text


def test_year_bounds_ignores_longer_digit_runs():
    # 五位以上数字不应被当成年份，避免把「12345」解析成 1234
    assert year_bounds("共 123456 人") == (None, None)


def test_geo_zero_is_valid():
    # 0 是合法经纬度（赤道 / 本初子午线），禁止用真值判断
    assert is_valid_lat(0) is True
    assert is_valid_lng(0) is True
    assert has_coords(0, 0) is True
    assert coord_problem(0, 0) is None


def test_geo_rejects_out_of_range():
    assert is_valid_lat(91) is False
    assert is_valid_lng(181) is False
    assert coord_problem(91, 0) is not None
    assert has_coords(None, 116.4) is False
    assert has_coords("", "") is False
    assert has_coords(float("nan"), 116.4) is False


def test_entity_id_convention():
    import generate_report as G

    assert G.entity_id("person", "于谦") == "person:于谦"
    assert G.entity_id("place", "鄱阳湖") == "place:鄱阳湖"
    assert G.entity_id("org", "东林党") == "org:东林党"


def test_relation_id_is_content_addressed():
    import generate_report as G

    a = G.relation_id("于谦", "石亨", "敌对冲突", "p2-c10")
    b = G.relation_id("于谦", "石亨", "敌对冲突", "p2-c10")
    c = G.relation_id("石亨", "于谦", "敌对冲突", "p2-c10")
    assert a == b, "同内容必须同 ID（保证重跑不漂移）"
    assert a != c, "方向不同视为不同关系"
    assert a.startswith("relation:") and len(a) == len("relation:") + 12


def test_parse_factions_merges_donglin():
    import generate_report as G

    assert G.parse_factions("东林党人，官至左都御史") == ["东林党"]
    assert G.parse_factions("东林名士") == ["东林党"], "「东林」应归并到「东林党」"
    assert G.parse_factions("阉党头目") == ["阉党"]
    assert G.parse_factions("平民") == []
    assert G.parse_factions(None, "") == []


PROFILE_KEYS = {
    "raw", "label", "regime", "dynasty", "period", "factions", "orgs",
    "categories", "office", "origin", "jinshi_year", "note",
}


def test_faction_profile_shape_and_conservatism():
    """P2-03 的核心契约：字段集固定、空输入不臆造、原串可完整回查。"""
    from core import faction_profile as F

    empty = F.parse_profile(None)
    assert set(empty) == PROFILE_KEYS
    assert empty["raw"] == ""
    assert empty["regime"] is None and empty["dynasty"] is None and empty["period"] is None
    assert empty["factions"] == [] and empty["orgs"] == []
    assert empty["categories"] == [] and empty["office"] == []
    assert empty["origin"] is None and empty["jinshi_year"] is None


def test_faction_profile_parses_real_shapes():
    """真实脏串形态的解析锚点（改词表/正则时这些断言会先炸）。"""
    from core import faction_profile as F

    reign = F.reign_start_map([
        {"era": "嘉靖", "start": 1522}, {"era": "隆庆", "start": 1567},
        {"era": "万历", "start": 1573}, {"era": "建文", "start": 1399},
    ])

    p = F.parse_profile("明朝·兵科给事中（湖广应山人，万历三十五年1607进士）", "兵科给事中", reign)
    assert p["regime"] == "明朝" and p["dynasty"] == "明"
    assert p["office"] == ["兵科给事中"]
    assert p["origin"] == "湖广应山", "括号内「…人」应识别为籍贯"
    assert p["jinshi_year"] == 1607, "四位公元年夹在年号纪年里也要抽出来"
    assert p["note"] is None, "已识别的籍贯/科举不得重复落进备注"
    assert p["label"] == "兵科给事中"
    assert p["raw"].startswith("明朝·兵科给事中"), "原串必须原样保留"

    # 年号 + 汉数换算：真实串里最常见的形式（「万历五年进士」）
    q = F.parse_profile("明朝·内阁首辅（宁波人，隆庆二年进士）", "", reign)
    assert q["jinshi_year"] == 1568, "隆庆二年 = 1567 + 2 - 1"
    assert q["origin"] == "宁波"
    assert "内阁首辅" in q["orgs"] + q["office"]

    # 「嘉靖朝内阁」这类「时期+机构」拼接要拆开，但「建文朝廷」不能被误拆
    r = F.parse_profile("明朝·嘉靖朝内阁", "", reign)
    assert r["period"] == "嘉靖朝" and "内阁" in r["orgs"]
    s = F.parse_profile("建文朝廷", "", reign)
    assert s["regime"] == "建文朝廷", "精确政权名必须优先于时期拆分"


def test_faction_profile_leaves_unknown_blank():
    """宁可留空不可猜错：没有年份的「进士」不得臆造年份。"""
    from core import faction_profile as F

    p = F.parse_profile("明朝·福建进士", "", {})
    assert p["jinshi_year"] is None
    assert p["origin"] is None


def test_faction_profile_label_priority():
    """卡面「势力」标签优先级：派系 > 身份类别 > 机构 > 官职 > 政权。"""
    from core import faction_profile as F

    assert F.parse_profile("明朝·阉党·文官")["label"] == "阉党"
    assert F.parse_profile("明朝·锦衣卫")["label"] == "锦衣卫"
    assert F.parse_profile("明朝")["label"] == "明朝"


def test_factions_from_role_requires_self_identification():
    """role 里的派系只在「自我认同」句式下才算；叙述句不能算到自己头上。"""
    from core import faction_profile as F

    assert F.factions_from_role("东林党要角，官至左都御史") == ["东林党"]
    assert F.factions_from_role("浙党首辅，保杨镐，被东林借杨镐事攻击。") == ["浙党"]
    assert F.factions_from_role("被东林党人弹劾") == []
    assert F.factions_in("被东林借杨镐事攻击") == ["东林党"], "宽松扫描用于「势力」字段本身"


def test_profile_stats_counts_filled_and_unclassified():
    from core import faction_profile as F

    stats = F.profile_stats([F.parse_profile("明朝·锦衣卫"), F.parse_profile("……")])
    assert stats["total"] == 2
    assert stats["filled"]["regime"] == 1
    assert stats["unclassified"] == 1


def test_reign_start_map_ignores_incomplete_rows():
    from core import faction_profile as F

    table = F.reign_start_map([{"era": "万历", "start": 1573}, {"era": "缺年份"}, {"start": 1400}])
    assert table == {"万历": 1573}
