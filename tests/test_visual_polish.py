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
    # 首次迁移时模板可能还是 legacy 独立 style；同步后必须变成带来源标记的生成镜像。
    converted = ST.render_template(skeleton, theme)
    assert theme.rstrip() in converted
    assert converted.count(ST.SOURCE_ATTR) == 1
    assert converted.count(ST.START) == 1
    assert converted.count(ST.END) == 1
    # 同步器必须幂等，否则发布工作流会不断制造无意义提交。
    assert ST.render_template(converted, theme) == converted


def test_v2_information_architecture_hooks_exist():
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    # 12 个原视图一个不少，只改变信息架构，不改业务 view id。
    expected = (
        "overview", "distribution", "timeline", "dynasty", "chronicle",
        "characters", "locations", "events", "relations",
        "visuals", "map", "insight",
    )
    for view in expected:
        assert skeleton.count('data-view="%s"' % view) == 1, view
    assert skeleton.count('class="nav-cluster"') == 3
    for label in ("全局叙事", "实体索引", "探索分析"):
        assert 'aria-label="%s"' % label in skeleton

    # 首页探索路径应复用 app.js 已有的 data-open-view 委托，而不是复制 setView。
    assert "V2 首页探索路径" in skeleton
    assert "MutationObserver" in skeleton
    assert "function setView" not in skeleton
    for view in ("characters", "relations", "visuals", "timeline", "dynasty", "chronicle", "map", "distribution", "insight"):
        assert 'data-open-view=\"%s\"' % view in skeleton


def test_v2_visual_language_is_shared_across_views():
    theme = ST.THEME.read_text(encoding="utf-8")
    for token in (
        ".v2-journey-grid", ".visuals-panel::before", ".map-wrap::before",
        ".timeline{", ".chronicle-wrap{", ".dynasty-band{",
    ):
        assert token in theme, token
    assert "scroll-margin-top:122px" in theme


def test_web_target_copies_service_worker_and_reports_all_assets():
    payload = _support.payload("full")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        written = B.render_web(payload, out)

        assert (out / "index.html").exists()
        assert (out / "assets" / "app.css").exists()
        assert (out / "assets" / "app.js").exists()
        assert (out / "assets" / "data.js").exists()
        assert (out / "sw.js").exists(), "web target 必须带上 app.js 实际注册的 worker"
        assert (out / "sw.js").read_text(encoding="utf-8") == B.SW_PATH.read_text(encoding="utf-8")

        for name in ("index.html", "assets/app.css", "assets/app.js", "assets/data.js", "sw.js"):
            assert name in written, "构建统计漏报 %s" % name
            assert written[name] > 0


def test_service_worker_cache_bumped_for_frontend_change():
    sw = B.SW_PATH.read_text(encoding="utf-8")
    assert "CACHE_PREFIX + 'v11'" in sw
    assert "V2" in sw
