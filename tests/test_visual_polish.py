# -*- coding: utf-8 -*-
"""视觉 / 可访问性与 web target 资源完整性的回归检查。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import _support
import build as B
import sync_theme as ST


def test_visual_polish_and_a11y_hooks_exist():
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    assert 'name="theme-color"' in skeleton
    assert 'name="color-scheme"' in skeleton
    assert 'class="skip-link" href="#mainContent"' in skeleton
    assert '<main class="shell" id="mainContent" tabindex="-1">' in skeleton
    assert 'class="muted app-footer"' in skeleton
    assert "Visual polish 2026-09" in skeleton
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


def test_v2_information_architecture_hooks_exist():
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    expected = ("overview","distribution","timeline","dynasty","chronicle","characters","locations","events","relations","visuals","map","insight")
    for view in expected: assert skeleton.count('data-view="%s"' % view) == 1, view
    assert skeleton.count('class="nav-cluster"') == 3
    for label in ("全局叙事", "实体索引", "探索分析"): assert 'aria-label="%s"' % label in skeleton
    assert "V2 首页探索路径" in skeleton
    assert "MutationObserver" in skeleton
    assert "function setView" not in skeleton


def test_v2_visual_language_is_shared_across_views():
    theme = ST.THEME.read_text(encoding="utf-8")
    for token in (".v2-journey-grid", ".visuals-panel::before", ".map-wrap::before", ".timeline{", ".chronicle-wrap{", ".dynasty-band{"):
        assert token in theme, token
    assert "scroll-margin-top:122px" in theme


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
        for obsolete in ("data.js", "data-full.js", "data-character-details.js", "data-location-details.js", "data-space.js"):
            assert not (out / "assets" / obsolete).exists()
        assert (out / "sw.js").read_bytes() == B.SW_PATH.read_bytes()
        assert written["sw.js"] == len(B.SW_PATH.read_bytes())


def test_service_worker_cache_bumped_for_frontend_change():
    sw = B.SW_PATH.read_text(encoding="utf-8")
    assert "CACHE_PREFIX + 'v19'" in sw
    assert "V10" in sw
    assert "location-detail" in sw
    assert "8" in sw
