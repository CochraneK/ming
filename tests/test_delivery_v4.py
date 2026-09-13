# -*- coding: utf-8 -*-
"""V4 双交付基线：在线资源拆分与离线单文件必须来自同一构建入口。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import build
import generate_report as G
import sync_readme

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
            "assets/boot-data.js",
            "assets/data-full.js",
            "assets/data-loader.js",
            "assets/app.js",
            "assets/lazy-data.js",
            "assets/experience.js",
            "sw.js",
        }
        assert required.issubset(stats)
        assert all((out / name).exists() for name in required)
        assert '<link rel="stylesheet" href="assets/app.css">' in html
        assert '<link rel="stylesheet" href="assets/theme.css">' in html
        assert '<link rel="stylesheet" href="assets/experience.css">' in html
        assert '<script src="assets/boot-data.js"></script>' in html
        assert '<script src="assets/data-loader.js"></script>' in html
        assert '<script src="assets/app.js"></script>' in html
        assert '<script src="assets/lazy-data.js"></script>' in html
        assert '<script src="assets/experience.js"></script>' in html
        assert "assets/data-full.js" not in html
        assert "THEME_SYNC_START" not in html
        assert "EXPERIENCE_CSS_SYNC_START" not in html
        assert "EXPERIENCE_SYNC_START" not in html
        assert "const DATA=" not in html
    finally:
        td.cleanup()


def test_web_shell_is_small_and_heavy_data_is_separate():
    td, out, _stats = _web_output()
    try:
        html_size = (out / "index.html").stat().st_size
        boot_size = (out / "assets" / "boot-data.js").stat().st_size
        full_size = (out / "assets" / "data-full.js").stat().st_size
        assert html_size < 80 * 1024
        assert boot_size < 96 * 1024
        assert full_size > boot_size * 10
    finally:
        td.cleanup()


def test_default_full_standalone_does_not_overwrite_online_index():
    assert build._default_out("full", "standalone") == ROOT / "standalone.html"
    assert build._default_out("full", "web") == ROOT / "dist" / "full"


def test_refresh_workflow_publishes_web_root_and_keeps_standalone():
    text = (ROOT / ".github" / "workflows" / "refresh-index.yml").read_text(encoding="utf-8")
    assert "--target web" in text
    assert "standalone.html" in text
    assert "cp -R .ci/publish/assets assets" in text
    assert "git add" in text and "assets" in text and "standalone.html" in text


def test_readme_sync_documents_dual_delivery_idempotently():
    source = sync_readme.README.read_text(encoding="utf-8")
    rendered = sync_readme.render_readme(source)
    assert "在线版采用分离资源交付" in rendered
    assert "`standalone.html` 单文件离线版" in rendered
    assert "构建全书单文件 standalone.html" in rendered
    assert "assets/experience.js" in rendered
    assert "在线 `index.html + assets/` 与离线 `standalone.html`" in rendered
    assert sync_readme.render_readme(rendered) == rendered
