# -*- coding: utf-8 -*-
"""V5 boot/full 基线 + V6 search-index 门控回归。"""
from __future__ import annotations

import json
from pathlib import Path

import build
import generate_report as G
import sync_lazy_data

ROOT = Path(__file__).resolve().parents[1]


def _compact_bytes(value) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def test_boot_payload_is_small_and_only_keeps_overview_data():
    payload = G.build_scope("full")
    boot, full = build.split_web_payload(payload)
    assert _compact_bytes(boot) < 96 * 1024
    for key in build.WEB_BOOT_KEYS:
        assert boot[key] == payload[key]
        assert key not in full
    for key in ("characters", "locations", "events", "relations"):
        assert boot[key] == []
        assert full[key] == payload[key]
    assert boot["chapters"] == {}
    assert full["chapters"] == payload["chapters"]
    assert len(boot["relationGraphFull"]["nodes"]) <= 1
    assert full["relationGraphFull"] == payload["relationGraphFull"]


def test_boot_plus_full_reconstructs_final_payload_losslessly():
    payload = G.build_scope("full")
    boot, full = build.split_web_payload(payload)
    merged = dict(boot)
    merged.update(full)
    assert merged == payload


def test_lazy_loader_and_gate_have_expected_contract():
    loader = (ROOT / "web" / "js" / "data-loader.js").read_text(encoding="utf-8")
    gate = (ROOT / "web" / "js" / "lazy-data.js").read_text(encoding="utf-8")
    assert "__MING_ENSURE_FULL_DATA" in loader
    assert "__MING_ENSURE_SEARCH_INDEX" in loader
    assert "deepHashNeedsFull" in loader
    assert "document.write" in loader
    assert "assets/search-index.js" in loader
    assert "assets/data-full.js" in loader
    assert "__MING_FULL_DATA_READY" in loader
    assert "__MING_SEARCH_INDEX_READY" in loader
    assert "const baseSetView=setView" in gate
    assert "正在加载完整知识库" in gate
    assert "__MING_AFTER_FULL_DATA" in gate


def test_command_palette_search_index_hook_is_idempotent():
    source = sync_lazy_data.TARGET.read_text(encoding="utf-8")
    rendered = sync_lazy_data.render_source(source)
    assert sync_lazy_data.MARKER in rendered
    assert "commandHasSearchIndex" in rendered
    assert "__MING_ENSURE_SEARCH_INDEX('command')" in rendered
    assert "__MING_ENSURE_FULL_DATA('command-result:'" in rendered
    assert "__MING_ENSURE_FULL_DATA('command')" not in rendered
    assert sync_lazy_data.render_source(rendered) == rendered
