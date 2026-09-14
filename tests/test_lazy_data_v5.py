# -*- coding: utf-8 -*-
"""V5/V6 按需基线 + V7~V10 领域、人物/地点摘要与详情分片回归。"""
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
    assert boot["chapterLocations"] == []
    assert boot["voyages"] == {}
    assert len(boot["relationGraphFull"]["nodes"]) <= 1
    assert set(chunks) == set(build.WEB_CHUNKS)


def test_boot_plus_domain_chunks_reconstruct_final_payload_losslessly():
    payload = G.build_scope("full")
    boot, chunks = build.split_web_chunks(payload)
    assert build.reconstruct_web_payload(boot, chunks) == payload
    delivery = build.split_delivery_chunks(chunks)
    assert build.reconstruct_web_payload_from_delivery(boot, delivery) == payload


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


def test_location_cards_are_light_and_context_is_deferred():
    payload = G.build_scope("full")
    _boot, chunks = build.split_web_chunks(payload)
    cards = chunks["locations"]["locations"]
    details = chunks["location-details"]["details"]
    assert len(cards) == len(payload["locations"]) == len(details)
    assert _compact_bytes(chunks["locations"]) < 512 * 1024
    assert _compact_bytes(chunks["locations"]) < _compact_bytes(payload["locations"])
    assert all(len(x.get("mentionContext") or []) <= 3 for x in cards)
    assert all(len(x.get("chapters") or []) <= 6 for x in cards)
    assert all(len(x.get("directEvents") or []) <= 6 for x in cards)
    assert any("relatedEvents" in extra for extra in details.values())
    assert any("relatedPeople" in extra or "note" in extra for extra in details.values())


def test_character_detail_shards_are_deterministic_exhaustive_and_bounded():
    payload = G.build_scope("full")
    _boot, logical = build.split_web_chunks(payload)
    physical = build.split_delivery_chunks(logical)
    assert set(physical) == set(build.WEB_DELIVERY_CHUNKS)
    detail_names = []
    shard_sizes = []
    for shard in build.CHARACTER_DETAIL_SHARD_NAMES:
        rows = physical[shard]["details"]
        detail_names.extend(rows)
        shard_sizes.append(_compact_bytes(physical[shard]))
        for person in rows:
            assert build.character_detail_shard_name(person) == shard
    assert sorted(detail_names) == sorted(logical["character-details"]["details"])
    assert len(detail_names) == len(set(detail_names)) == len(payload["characters"])
    assert max(shard_sizes) < 192 * 1024
    assert build.character_detail_shard_name("于谦") == "character-detail-13"
    assert build.character_detail_shard_name("王守仁") == "character-detail-07"


def test_location_detail_shards_are_deterministic_exhaustive_and_bounded():
    payload = G.build_scope("full")
    _boot, logical = build.split_web_chunks(payload)
    physical = build.split_delivery_chunks(logical)
    detail_names = []
    shard_sizes = []
    for shard in build.LOCATION_DETAIL_SHARD_NAMES:
        rows = physical[shard]["details"]
        detail_names.extend(rows)
        shard_sizes.append(_compact_bytes(physical[shard]))
        for place in rows:
            assert build.location_detail_shard_name(place) == shard
    assert sorted(detail_names) == sorted(logical["location-details"]["details"])
    assert len(detail_names) == len(set(detail_names)) == len(payload["locations"])
    assert max(shard_sizes) < 128 * 1024
    assert build.location_detail_shard_name("宁远") == "location-detail-00"
    assert build.location_detail_shard_name("南京") == "location-detail-06"


def test_domain_fields_are_mutually_exclusive_and_exhaustive():
    payload = G.build_scope("full")
    claimed = list(build.WEB_BOOT_KEYS) + ["characters", "locations"]
    for fields in build.WEB_CHUNK_FIELDS.values():
        claimed.extend(fields)
    assert len(claimed) == len(set(claimed))
    assert set(claimed) == set(payload)
    for virtual in ("character-details", "location-details"):
        assert virtual in build.WEB_CHUNKS
        assert virtual not in build.WEB_DELIVERY_CHUNKS
        assert virtual not in payload


def test_lazy_loader_and_gate_have_v10_contract():
    loader = (ROOT / "web" / "js" / "data-loader.js").read_text(encoding="utf-8")
    gate = (ROOT / "web" / "js" / "lazy-data.js").read_text(encoding="utf-8")
    for token in (
        "__MING_ENSURE_DATA_CHUNKS", "__MING_ENSURE_VIEW_DATA", "__MING_ENSURE_ENTITY_DATA",
        "__MING_ENSURE_FULL_DATA", "__MING_ENSURE_SEARCH_INDEX", "VIEW_CHUNKS", "ENTITY_CHUNKS",
        "CHARACTER_DETAIL_SHARD_COUNT=16", "LOCATION_DETAIL_SHARD_COUNT=8",
        "characterDetailChunkFor", "locationDetailChunkFor", "__MING_ENTITY_PLAN",
        "__MING_CHARACTER_DETAILS__", "__MING_LOCATION_DETAILS__",
        "__MING_APPLY_CHARACTER_DETAILS__", "__MING_APPLY_LOCATION_DETAILS__",
        "character-detail-", "location-detail-", "assets/data-'", "document.write",
    ):
        assert token in loader, token
    assert "assets/data-full.js" not in loader
    assert "__MING_FULL_DATA_READY" in loader
    assert "locations:['locations']" in loader
    assert "map:['locations']" in loader
    assert "if(kind==='person')return ['characters',characterDetailChunkFor(id),'events','insight']" in loader
    assert "if(kind==='place')return ['locations',locationDetailChunkFor(id),'events','insight']" in loader
    assert "function entityReady(kind,id)" in gate
    assert "__MING_ENSURE_ENTITY_DATA(kind,'entity:'+kind,id)" in gate
    assert "[data-loc-mode=\"chapter\"]" in gate
    assert "['place-chapters']" in gate
    assert "[data-map-mode=\"voyage\"]" in gate
    assert "['voyages','events']" in gate
    assert "[data-location-id]" in gate
    assert "location-card:" in gate
    assert "const baseSetView=setView" in gate
    assert "正在加载此视图所需数据" in gate
    assert "const baseShowPerson" in gate
    assert "const baseShowEvent" in gate
    assert "const baseShowLocation" in gate
    assert "insight-link:" in gate
    assert "__MING_AFTER_DATA_CHUNKS" in gate


def test_command_palette_passes_entity_id_for_detail_shard_and_is_idempotent():
    source = sync_lazy_data.TARGET.read_text(encoding="utf-8")
    rendered = sync_lazy_data.render_source(source)
    assert sync_lazy_data.MARKER in rendered
    assert "commandHasSearchIndex" in rendered
    assert "__MING_ENSURE_SEARCH_INDEX('command')" in rendered
    assert "__MING_ENSURE_ENTITY_DATA(r.kind,'command-result:'+r.kind,r.id)" in rendered
    assert "__MING_ENSURE_FULL_DATA('command-result:'" in rendered
    assert rendered.index("__MING_ENSURE_ENTITY_DATA") < rendered.index("__MING_ENSURE_FULL_DATA('command-result:'")
    assert sync_lazy_data.render_source(rendered) == rendered
