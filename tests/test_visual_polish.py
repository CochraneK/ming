# -*- coding: utf-8 -*-
"""视觉 / 可访问性与 web target 资源完整性的回归检查。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import _support
import build as B


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
    assert "CACHE_PREFIX + 'v10'" in sw
    assert "web target" in sw
