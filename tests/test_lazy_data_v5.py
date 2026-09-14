# -*- coding: utf-8 -*-
"""V5/V6 按需基线 + V7/V8 领域与人物详情二级分区回归。"""
from __future__ import annotations

import json
from pathlib import Path

import build
import generate_report as G
import sync_lazy_data

ROOT = Path(__file__).resolve().parents[1]


def _compact_bytes(value) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def test_boot_payload_is_small_and_keeps_zero_request_views_ready():
    payload = G.build_scope("full")
    boot, chunks = build.split_web_chunks(payload)
    assert _compact_bytes(boot) < 112 * 1024
    for key in build.WEB_BOOT_KEYS:
        assert boot[key] == payload[key]
    for key in ("characters", "locations", "events", "relations"):
        assert boot[key] == []
    assert boot["chapters"] == {}
    assert len(boot["relationGraphFull"]["nodes"]) <= 1
    assert set(chunks) == set(build.WEB_CHUNKS)


def test_boot_plus_domain_chunks_reconstruct_final_payload_losslessly():
    payload = G.build_scope("full")
    boot, chunks = build.split_web_chunks(payload)
    assert build.reconstruct_web_payload(boot, chunks) == payload


def test_character_cards_are_light_and_details_are_deferred():
    payload = G.build_scope("full")
    _boot, chunks = build.split_web_chunks(payload)
    cards = chunks["characters"]["characters"]
    details = chunks["character-details"]["details"]
    assert len(cards) == len(payload["characters"]) == len(details)
    assert _compact_bytes(chunks["characters"]) < 1024 * 1024
    assert _compact_bytes(chunks["characters"]) < _compact_bytes(payload["characters"])
    assert all(len(x.get("events") or []) <= 3 for x in cards)
    assert all(len(x.get("contextEvents") or []) <= 3 for x in cards)
    assert all(set((x.get("profile") or {})) <= set(build.CHARACTER_CARD_PROFILE_KEYS) for x in cards)
    assert any("relations" in extra for extra in details.values())
    assert any("profile" in extra for extra in details.values())


def test_domain_fields_are_mutually_exclusive_and_exhaustive():
    payload = G.build_scope("full")
    claimed = list(build.WEB_BOOT_KEYS) + ["characters"]
    for fields in build.WEB_CHUNK_FIELDS.values():
        claimed.extend(fields)
    assert len(claimed) == len(set(claimed))
    assert set(claimed) == set(payload)
    assert "character-details" in build.WEB_CHUNKS
    assert "character-details" not in payload


def test_lazy_loader_and_gate_have_v8_contract():
    loader = (ROOT / "web" / "js" / "data-loader.js").read_text(encoding="utf-8")
    gate = (ROOT / "web" / "js" / "lazy-data.js").read_text(encoding="utf-8")
    for token in (
        "__MING_ENSURE_DATA_CHUNKS", "__MING_ENSURE_VIEW_DATA", "__MING_ENSURE_ENTITY_DATA",
        "__MING_ENSURE_FULL_DATA", "__MING_ENSURE_SEARCH_INDEX", "VIEW_CHUNKS", "ENTITY_CHUNKS",
        "character-details", "__MING_CHARACTER_DETAILS__", "__MING_APPLY_CHARACTER_DETAILS__",
        "assets/data-'", "document.write",
    ):
        assert token in loader, token
    assert "assets/data-full.js" not in loader
    assert "__MING_FULL_DATA_READY" in loader
    assert "characters:['characters']" in loader
    assert "person:['characters','character-details','events','insight']" in loader
    assert "const baseSetView=setView" in gate
    assert "正在加载此视图所需数据" in gate
    assert "const baseShowPerson" in gate
    assert "const baseShowEvent" in gate
    assert "const baseShowLocation" in gate
    assert "insight-link:" in gate
    assert "__MING_AFTER_DATA_CHUNKS" in gate


def test_command_palette_uses_entity_chunks_not_full_and_is_idempotent():
    source = sync_lazy_data.TARGET.read_text(encoding="utf-8")
    rendered = sync_lazy_data.render_source(source)
    assert sync_lazy_data.MARKER in rendered
    assert "commandHasSearchIndex" in rendered
    assert "__MING_ENSURE_SEARCH_INDEX('command')" in rendered
    assert "__MING_ENSURE_ENTITY_DATA(r.kind,'command-result:'" in rendered
    assert "__MING_ENSURE_FULL_DATA('command-result:'" in rendered  # 仅旧浏览器/无 loader fallback
    assert rendered.index("__MING_ENSURE_ENTITY_DATA") < rendered.index("__MING_ENSURE_FULL_DATA('command-result:'")
    assert sync_lazy_data.render_source(rendered) == rendered
