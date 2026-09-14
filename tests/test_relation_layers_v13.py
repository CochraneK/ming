# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
from pathlib import Path

import _support
import build
import split_relation_asset_v13 as V13

ROOT = Path(__file__).resolve().parents[1]
CORE_KEYS = {"from", "to", "rel", "category", "sourceTitle"}


def test_v13_relation_postprocess_is_lossless_and_idempotent():
    payload = _support.payload("full")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        build.render_web(payload, out)
        original = V13.read_chunk_payload(out / "assets" / "data-relations.js")["relations"]
        stats = V13.split_site(out)
        core = V13.read_chunk_payload(out / "assets" / "data-relations.js")["relations"]
        meta = V13.read_relation_meta(out / "assets" / "data-relation-meta.js")
        assert V13.reconstruct_relations(core, meta) == original
        assert stats["relation_count"] == len(payload["relations"])
        assert len(core) == len(meta) == len(original)
        assert all(set(row) == CORE_KEYS for row in core)
        assert any("id" in patch for patch in meta)
        assert V13.split_site(out) == V13.check_site(out)


def test_v13_relation_core_is_smaller_than_original_transport():
    payload = _support.payload("full")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        build.render_web(payload, out)
        before = (out / "assets" / "data-relations.js").stat().st_size
        stats = V13.split_site(out)
        assert stats["relations_bytes"] < before
        assert stats["relations_bytes"] < 448 * 1024
        assert stats["meta_bytes"] < 640 * 1024


def test_v13_loader_defers_relation_metadata_from_relation_view():
    loader = (ROOT / "web" / "js" / "data-loader.js").read_text(encoding="utf-8")
    assert "'relations','relation-meta','time'" in loader
    assert "relations:['relations']" in loader
    assert "relations:['relations','relation-meta']" not in loader
    assert "__MING_RELATION_META__" in loader
    assert "__MING_APPLY_RELATION_META__" in loader
    assert "name==='relations'||name==='relation-meta'" in loader
