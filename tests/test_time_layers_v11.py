# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
from pathlib import Path

import _support
import build
import split_time_asset_v11 as V11

ROOT = Path(__file__).resolve().parents[1]


def test_v11_time_postprocess_is_lossless_and_idempotent():
    payload = _support.payload("full")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        build.render_web(payload, out)
        original = V11.read_chunk_payload(out / "assets" / "data-time.js")
        assert "lifespans" in original
        stats = V11.split_site(out)
        time_payload = V11.read_chunk_payload(out / "assets" / "data-time.js")
        life_payload = V11.read_chunk_payload(out / "assets" / "data-lifespans.js")
        reconstructed = dict(time_payload)
        reconstructed.update(life_payload)
        assert reconstructed == original
        assert "lifespans" not in time_payload
        assert set(life_payload) == {"lifespans"}
        assert stats["lifespans_count"] == len(payload["lifespans"])
        assert V11.split_site(out) == V11.check_site(out)


def test_v11_lifespans_asset_is_small_and_reduces_chronicle_route():
    payload = _support.payload("full")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        build.render_web(payload, out)
        before = (out / "assets" / "data-time.js").stat().st_size
        V11.split_site(out)
        time_size = (out / "assets" / "data-time.js").stat().st_size
        life_size = (out / "assets" / "data-lifespans.js").stat().st_size
        char_size = (out / "assets" / "data-characters.js").stat().st_size
        assert life_size < 64 * 1024
        assert time_size < before
        assert char_size + life_size < 512 * 1024
        assert char_size + life_size < char_size + before


def test_v11_loader_routes_chronicle_to_lifespans_only():
    loader = (ROOT / "web" / "js" / "data-loader.js").read_text(encoding="utf-8")
    assert "V11 在线数据加载器" in loader
    assert "'time','lifespans','graphs'" in loader
    assert "timeline:['time','events']" in loader
    assert "dynasty:['time','events']" in loader
    assert "chronicle:['lifespans','characters']" in loader
    assert "chronicle:['time','characters']" not in loader
