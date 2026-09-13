# -*- coding: utf-8 -*-
"""V3 产品体验增强层：单一源、无侵入与关键交互钩子。"""
from __future__ import annotations

import build as B
import sync_experience as SE


def test_experience_sources_sync_idempotently_into_template():
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    css = SE.CSS_SOURCE.read_text(encoding="utf-8")
    js = SE.JS_SOURCE.read_text(encoding="utf-8")
    converted = SE.render_template(skeleton, css, js)

    assert css.rstrip() in converted
    assert js.rstrip() in converted
    for token in (
        SE.STYLE_ATTR, SE.SCRIPT_ATTR, SE.STYLE_START, SE.STYLE_END,
        SE.SCRIPT_START, SE.SCRIPT_END,
    ):
        assert converted.count(token) == 1, token
    # 产品增强层必须在主 app.js 之后执行，才能复用 setView/show*/graph helpers。
    assert converted.index(SE.SCRIPT_ATTR) > converted.index("/*{{INLINE_JS}}*/")
    assert SE.render_template(converted, css, js) == converted


def test_command_palette_covers_views_and_three_entity_types():
    js = SE.JS_SOURCE.read_text(encoding="utf-8")
    for token in (
        "全局搜索", "⌘/Ctrl K", "DATA.characters", "DATA.locations", "DATA.events",
        "aliases", "showPerson", "showLocation", "showEvent", "window.__MING_EXPERIENCE_READY=true",
    ):
        assert token in js, token
    # 渐进增强层不得复制核心业务渲染器。
    for forbidden in ("function renderCharacters", "function renderLocations", "function renderEvents", "function setView"):
        assert forbidden not in js, forbidden


def test_home_story_is_metric_driven_not_hardcoded():
    js = SE.JS_SOURCE.read_text(encoding="utf-8")
    assert "DATA.metrics.locatedLocations" in js
    assert "DATA.metrics.timedEvents" in js
    assert "DATA.relationGraphFull" in js
    assert "DATA.distribution" in js
    assert "数据覆盖与结构信号" in js
    # 旧 README 曾出现过 581 地点；体验层不能重新引入这种会漂移的硬编码口径。
    assert "581" not in js


def test_graph_reader_reuses_existing_focus_mechanism():
    js = SE.JS_SOURCE.read_text(encoding="utf-8")
    for token in (
        "v3-graph-reader", "showFullNode", "resetFullHighlight", "12% 不透明度",
        "高连接入口", "实体图包含人物、地点、机构、政权",
    ):
        assert token in js, token


def test_experience_css_has_responsive_and_print_guards():
    css = SE.CSS_SOURCE.read_text(encoding="utf-8")
    for token in (
        ".command-shell", ".v3-story-grid", ".v3-graph-reader",
        "@media(max-width:640px)", "@media print",
    ):
        assert token in css, token
