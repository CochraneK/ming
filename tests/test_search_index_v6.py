# -*- coding: utf-8 -*-
"""V6 轻量搜索目录：覆盖实体、无详情复制、体积受控。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import build
import generate_report as G


def _bytes(value) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def test_search_index_covers_all_searchable_entities_without_raw_objects():
    payload = G.build_scope("full")
    index = build.build_search_index(payload)
    rows = index["rows"]
    assert len(rows) == len(payload["characters"]) + len(payload["locations"]) + len(payload["events"])
    assert {r["kind"] for r in rows} == {"person", "place", "event"}
    assert all(set(r) == {"kind", "id", "title", "meta", "search"} for r in rows)
    assert all("raw" not in r for r in rows)

    assert any(r["kind"] == "person" and r["title"] == "于谦" and "于谦" in r["search"] for r in rows)
    assert any(r["kind"] == "place" and r["title"] == "宁远" for r in rows)
    first_event = payload["events"][0]
    assert any(r["kind"] == "event" and r["id"] == first_event["id"] for r in rows)


def test_search_index_has_independent_hard_budget():
    payload = G.build_scope("full")
    index = build.build_search_index(payload)
    assert _bytes(index) < 768 * 1024
    assert _bytes(index) < _bytes(payload) // 5


def test_web_target_emits_search_index_but_does_not_eagerly_reference_it():
    payload = G.build_scope("p1")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        stats = build.render_web(payload, out)
        search = out / "assets" / "search-index.js"
        html = (out / "index.html").read_text(encoding="utf-8")
        assert search.exists()
        assert "assets/search-index.js" in stats
        assert "window.__MING_SEARCH_INDEX__=" in search.read_text(encoding="utf-8")
        assert "assets/search-index.js" not in html
        assert "assets/data-full.js" not in html
