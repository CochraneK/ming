# -*- coding: utf-8 -*-
"""V4 双交付：在线资源拆分与离线单文件必须来自同一构建入口。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import build
import generate_report as G

ROOT = Path(__file__).resolve().parents[1]


def _web_output():
    td = tempfile.TemporaryDirectory()
    out = Path(td.name) / "site"
    payload = G.build_scope("p1")
    stats = build.render_web(payload, out)
    return td, out, stats


def test_web_target_externalizes_every_project_frontend_layer():
    td, out, stats = _web_output()
    try:
        html = (out / "index.html").read_text(encoding="utf-8")
        required = {
            "assets/app.css",
            "assets/theme.css",
            "assets/experience.css",
            "assets/data.js",
            "assets/app.js",
            "assets/experience.js",
            "sw.js",
        }
        assert required.issubset(stats)
        assert all((out / name).exists() for name in required)
        assert '<link rel="stylesheet" href="assets/app.css">' in html
        assert '<link rel="stylesheet" href="assets/theme.css">' in html
        assert '<link rel="stylesheet" href="assets/experience.css">' in html
        assert '<script src="assets/data.js"></script>' in html
        assert '<script src="assets/app.js"></script>' in html
        assert '<script src="assets/experience.js"></script>' in html
        assert "THEME_SYNC_START" not in html
        assert "EXPERIENCE_CSS_SYNC_START" not in html
        assert "EXPERIENCE_SYNC_START" not in html
        assert "const DATA=" not in html
    finally:
        td.cleanup()


def test_web_shell_is_small_and_data_is_separate():
    td, out, _stats = _web_output()
    try:
        html_size = (out / "index.html").stat().st_size
        data_size = (out / "assets" / "data.js").stat().st_size
        assert html_size < 80 * 1024
        assert data_size > html_size * 5
    finally:
        td.cleanup()


def test_refresh_workflow_publishes_web_root_and_keeps_standalone():
    text = (ROOT / ".github" / "workflows" / "refresh-index.yml").read_text(encoding="utf-8")
    assert "--target web" in text
    assert "standalone.html" in text
    assert "cp -R .ci/publish/assets assets" in text
    assert "git add" in text and "assets" in text and "standalone.html" in text
