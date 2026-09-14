# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
from pathlib import Path

import _support
import build
import split_event_asset_v12 as V12
import split_time_asset_v11 as V11
import sync_event_cards_v12

ROOT = Path(__file__).resolve().parents[1]


def _site():
    td = tempfile.TemporaryDirectory()
    out = Path(td.name) / "site"
    payload = _support.payload("full")
    build.render_web(payload, out)
    V11.split_site(out)
    V12.split_site(out)
    return td, out, payload


def test_v12_event_split_is_lossless_and_idempotent():
    payload = _support.payload("full")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        build.render_web(payload, out)
        V11.split_site(out)
        original = V12.read_chunk_payload(out / "assets" / "data-events.js")["events"]
        stats = V12.split_site(out)
        summaries = V12.read_chunk_payload(out / "assets" / "data-events.js")["events"]
        details, _sizes = V12._read_all_details(out / "assets")
        assert V12.reconstruct_events(summaries, details) == original
        assert stats["event_count"] == len(payload["events"])
        assert V12.split_site(out) == V12.check_site(out)


def test_v12_event_core_is_light_and_details_are_deferred():
    td, out, payload = _site()
    try:
        stats = V12.check_site(out)
        summaries = V12.read_chunk_payload(out / "assets" / "data-events.js")["events"]
        assert len(summaries) == len(payload["events"])
        assert stats["events_bytes"] < 320 * 1024
        assert stats["detail_max_bytes"] < 96 * 1024
        assert stats["detail_total_bytes"] < 384 * 1024
        assert all("sourceCount" in event for event in summaries)
        assert all("sources" not in event for event in summaries)
        assert all("year_source" not in event and "year_start" not in event for event in summaries)
    finally:
        td.cleanup()


def test_v12_event_shards_are_deterministic_exhaustive_and_bounded():
    td, out, payload = _site()
    try:
        summaries = V12.read_chunk_payload(out / "assets" / "data-events.js")["events"]
        details, sizes = V12._read_all_details(out / "assets")
        ids = [event["id"] for event in summaries]
        assert set(ids) == set(details)
        assert len(ids) == len(set(ids)) == len(payload["events"])
        assert len(sizes) == V12.EVENT_DETAIL_SHARD_COUNT == 8
        assert max(sizes.values()) < 96 * 1024
        assert V12.event_detail_shard_name("event-0001") == "event-detail-05"
        assert V12.event_detail_shard_name("event-0063") == "event-detail-01"
    finally:
        td.cleanup()


def test_v12_loader_routes_views_and_entities_lazily():
    loader = (ROOT / "web" / "js" / "data-loader.js").read_text(encoding="utf-8")
    gate = (ROOT / "web" / "js" / "lazy-data.js").read_text(encoding="utf-8")
    assert "EVENT_DETAIL_SHARD_COUNT=8" in loader
    assert "event-detail-" in loader
    assert "__MING_EVENT_DETAILS__" in loader
    assert "__MING_APPLY_EVENT_DETAILS__" in loader
    assert "timeline:['time']" in loader
    assert "dynasty:['time']" in loader
    assert "events:['events']" in loader
    assert "if(kind==='person')return ['characters',characterDetailChunkFor(id),'insight']" in loader
    assert "if(kind==='place')return ['locations',locationDetailChunkFor(id),'events','insight']" in loader
    assert "eventDetailChunkFor(eventId)" in loader
    assert "window.__MING_ENSURE_DATA_CHUNKS(['events'],why).then" in loader
    assert "[data-event-id],[data-event-name],[data-loc-event]" in gate
    assert "window.__MING_ENSURE_ENTITY_DATA('event','event-click:'+key,key)" in gate
    assert "window.__MING_ENSURE_DATA_CHUNKS(['voyages'],'map-voyage')" in gate
    assert "['voyages','events']" not in gate


def test_v12_event_list_source_count_sync_is_idempotent():
    source = sync_event_cards_v12.TARGET.read_text(encoding="utf-8")
    rendered = sync_event_cards_v12.render_source(source)
    assert sync_event_cards_v12.NEW in rendered
    assert sync_event_cards_v12.OLD not in rendered
    assert sync_event_cards_v12.render_source(rendered) == rendered
