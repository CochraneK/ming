# -*- coding: utf-8 -*-
"""V4 双交付基线 + V10 人物/地点详情分片与空间模式按需。"""
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
            "assets/app.css", "assets/theme.css", "assets/experience.css",
            "assets/boot-data.js", "assets/search-index.js", "assets/data-loader.js",
            "assets/app.js", "assets/lazy-data.js", "assets/experience.js", "sw.js",
        } | {"assets/data-%s.js" % name for name in build.WEB_DELIVERY_CHUNKS}
        assert required.issubset(stats)
        assert all((out / name).exists() for name in required)
        for eager in (
            "assets/app.css", "assets/theme.css", "assets/experience.css",
            "assets/boot-data.js", "assets/data-loader.js", "assets/app.js",
            "assets/lazy-data.js", "assets/experience.js",
        ):
            assert eager in html
        assert "assets/search-index.js" not in html
        for name in build.WEB_DELIVERY_CHUNKS:
            assert "assets/data-%s.js" % name not in html
        assert "THEME_SYNC_START" not in html
        assert "EXPERIENCE_CSS_SYNC_START" not in html
        assert "EXPERIENCE_SYNC_START" not in html
        assert "const DATA=" not in html
        for obsolete in ("data-full.js", "data-character-details.js", "data-location-details.js", "data-space.js"):
            assert not (out / "assets" / obsolete).exists()
    finally:
        td.cleanup()


def test_web_shell_and_entity_layers_are_small():
    td, out, _stats = _web_output()
    try:
        assert (out / "index.html").stat().st_size < 80 * 1024
        assert (out / "assets" / "boot-data.js").stat().st_size < 112 * 1024
        assert (out / "assets" / "search-index.js").stat().st_size < 768 * 1024
        sizes = {name: (out / "assets" / ("data-%s.js" % name)).stat().st_size for name in build.WEB_DELIVERY_CHUNKS}
        char_detail = [sizes[name] for name in build.CHARACTER_DETAIL_SHARD_NAMES]
        loc_detail = [sizes[name] for name in build.LOCATION_DETAIL_SHARD_NAMES]
        assert len(char_detail) == 16 and max(char_detail) < 192 * 1024
        assert len(loc_detail) == 8 and max(loc_detail) < 128 * 1024
        assert sizes["characters"] < 1024 * 1024
        assert sizes["locations"] < 512 * 1024
        assert sizes["place-chapters"] < 320 * 1024
        assert sizes["voyages"] < 64 * 1024
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


def test_readme_sync_documents_v10_delivery_idempotently():
    source = sync_readme.README.read_text(encoding="utf-8")
    rendered = sync_readme.render_readme(source)
    assert "在线版采用 V10 实体与空间分层按需交付" in rendered
    assert "`data-characters.js` + 16 个" in rendered
    assert "轻量 `data-locations.js`" in rendered
    assert "8 个 `data-location-detail-00.js`" in rendered
    assert "`data-place-chapters.js`" in rendered
    assert "`data-voyages.js`" in rendered
    assert "地点索引和默认地图只取地点摘要" in rendered
    assert "`standalone.html` 单文件离线版" in rendered
    assert "不维护 `data-full.js`" in rendered
    assert "旧 `data-space.js`" in rendered
    assert "在线 V10 `index.html + assets/` 与离线 `standalone.html`" in rendered
    assert sync_readme.render_readme(rendered) == rendered
