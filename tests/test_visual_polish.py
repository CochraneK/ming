# -*- coding: utf-8 -*-
"""Classic UI / 可访问性与 web target 资源完整性的回归检查。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import _support
import build as B
import sync_theme as ST


def test_classic_ui_and_a11y_hooks_exist():
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    assert 'name="theme-color"' in skeleton
    assert 'name="color-scheme"' in skeleton
    assert 'class="skip-link" href="#mainContent"' in skeleton
    assert '<main class="shell" id="mainContent" tabindex="-1">' in skeleton
    assert 'class="muted app-footer"' in skeleton
    assert "Classic UI compatibility layer" in skeleton
    assert ":focus-visible" in skeleton
    assert "prefers-reduced-motion:reduce" in skeleton


def test_theme_css_is_single_source_for_template_mirror():
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    theme = ST.THEME.read_text(encoding="utf-8")
    converted = ST.render_template(skeleton, theme)
    assert theme.rstrip() in converted
    assert converted.count(ST.SOURCE_ATTR) == 1
    assert converted.count(ST.START) == 1
    assert converted.count(ST.END) == 1
    assert ST.render_template(converted, theme) == converted


def test_original_twelve_button_navigation_is_restored():
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    expected = (
        "overview", "distribution", "visuals", "locations", "map", "characters",
        "events", "relations", "timeline", "dynasty", "chronicle", "insight",
    )
    positions = []
    for view in expected:
        token = 'data-view="%s"' % view
        assert skeleton.count(token) == 1, view
        positions.append(skeleton.index(token))
    assert positions == sorted(positions)
    assert 'class="nav-cluster"' not in skeleton
    for label in ("全局叙事", "实体索引", "探索分析", "V2 首页探索路径"):
        assert label not in skeleton


def test_classic_theme_does_not_reskin_base_app_css():
    theme = ST.THEME.read_text(encoding="utf-8")
    for forbidden in (
        ".nav-cluster", ".v2-journey-grid", ".visuals-panel::before",
        ".map-wrap::before", "radial-gradient", "backdrop-filter",
    ):
        assert forbidden not in theme, forbidden
    assert ".skip-link" in theme
    assert ":focus-visible" in theme


def test_web_target_copies_service_worker_and_reports_all_assets():
    payload = _support.payload("full")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td);written = B.render_web(payload, out)
        expected = {
            "index.html", "assets/app.css", "assets/theme.css", "assets/experience.css",
            "assets/app.js", "assets/boot-data.js", "assets/search-index.js",
            "assets/data-loader.js", "assets/lazy-data.js", "assets/experience.js", "sw.js",
        } | {"assets/data-%s.js" % name for name in B.WEB_DELIVERY_CHUNKS}
        for name in expected:
            assert (out / name).exists(), "web target 缺少 %s" % name
            assert name in written and written[name] > 0
        for obsolete in ("data.js", "data-full.js", "data-character-details.js", "data-location-details.js", "data-event-details.js", "data-space.js"):
            assert not (out / "assets" / obsolete).exists()
        assert (out / "sw.js").read_bytes() == B.SW_PATH.read_bytes()
        assert written["sw.js"] == len(B.SW_PATH.read_bytes())


def test_service_worker_cache_bumped_for_classic_ui_restore():
    sw = B.SW_PATH.read_text(encoding="utf-8")
    assert "CACHE_PREFIX + 'v23'" in sw
    assert "classic UI" in sw
    assert "relation-meta" in sw
    assert "event-detail" in sw
    assert "lifespans" in sw
    assert "location-detail" in sw
