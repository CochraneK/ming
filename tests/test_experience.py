# -*- coding: utf-8 -*-
"""Classic UI：体验镜像仍可同步，但不再注入可见 V2/V3 覆盖层。"""
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
    assert converted.index(SE.SCRIPT_ATTR) > converted.index("/*{{INLINE_JS}}*/")
    assert SE.render_template(converted, css, js) == converted


def test_classic_mode_disables_visible_v2_v3_overlays():
    css = SE.CSS_SOURCE.read_text(encoding="utf-8")
    js = SE.JS_SOURCE.read_text(encoding="utf-8")
    assert "Classic UI mode" in css
    assert "Classic UI mode" in js
    assert "window.__MING_EXPERIENCE_READY=true" in js
    for forbidden in (
        "commandPalette", "v3-story", "v3-graph-reader", "command-trigger",
        "function renderCharacters", "function renderLocations", "function renderEvents",
    ):
        assert forbidden not in js, forbidden
    for forbidden in (".command-shell", ".v3-story-grid", ".v3-graph-reader", ".command-trigger"):
        assert forbidden not in css, forbidden


def test_modern_delivery_remains_outside_experience_layer():
    loader = B.DATA_LOADER_JS_PATH.read_text(encoding="utf-8")
    lazy = B.LAZY_DATA_JS_PATH.read_text(encoding="utf-8")
    for token in (
        "__MING_ENSURE_DATA_CHUNKS", "character-detail-", "location-detail-",
        "event-detail-", "relation-meta", "lifespans",
    ):
        assert token in loader, token
    assert "__MING_ENSURE_VIEW_DATA" in lazy
