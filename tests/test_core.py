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
