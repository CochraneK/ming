# -*- coding: utf-8 -*-
"""V8 人物卡片 / 详情补丁的聚焦回归。"""
from __future__ import annotations

import build
import generate_report as G


def test_v8_character_transport_preserves_order_and_identity_keys():
    payload = G.build_scope("full")
    cards, details = build.split_character_transport(payload["characters"])
    assert [x["name"] for x in cards] == [x["name"] for x in payload["characters"]]
    assert set(details) == {x["name"] for x in payload["characters"]}
    assert len(details) == len(payload["characters"])


def test_v8_reconstruction_restores_nested_profile_and_relations_exactly():
    payload = G.build_scope("full")
    boot, chunks = build.split_web_chunks(payload)
    rebuilt = build.reconstruct_web_payload(boot, chunks)
    by_name = {x["name"]: x for x in rebuilt["characters"]}
    original = {x["name"]: x for x in payload["characters"]}
    for name in ("于谦", "王守仁", "朱元璋"):
        assert by_name[name] == original[name]
        assert by_name[name].get("profile") == original[name].get("profile")
        assert by_name[name].get("relations") == original[name].get("relations")
