# -*- coding: utf-8 -*-
"""最终前端 payload 的字段级体积剖析与 V10 人物/地点分片预算。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build as B  # noqa: E402
import generate_report as G  # noqa: E402

KIB = 1024
MIB = 1024 * 1024
BOOT_HARD = 112 * KIB
SEARCH_HARD = 768 * KIB
CHARACTERS_HARD = 1024 * KIB
CHAR_DETAIL_SHARD_HARD = 192 * KIB
CHAR_DETAIL_TOTAL_HARD = 2 * MIB
LOCATIONS_HARD = 512 * KIB
LOCATION_DETAIL_SHARD_HARD = 128 * KIB
LOCATION_DETAIL_TOTAL_HARD = 768 * KIB
PLACE_CHAPTERS_HARD = 320 * KIB
VOYAGES_HARD = 64 * KIB


def encoded_size(value) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _rows(delivery, names):
    rows = [{"name": name, "bytes": encoded_size(delivery[name])} for name in names]
    return sorted(rows, key=lambda x: (-x["bytes"], x["name"]))


def profile_payload(payload: dict) -> dict:
    fields = [{"key": key, "bytes": encoded_size(value)} for key, value in payload.items()]
    fields.sort(key=lambda x: (-x["bytes"], x["key"]))
    boot, logical = B.split_web_chunks(payload)
    delivery = B.split_delivery_chunks(logical)
    search = B.build_search_index(payload)
    domains = []
    for name in B.WEB_DELIVERY_CHUNKS:
        n = encoded_size(delivery[name])
        if name == "insight":
            n += encoded_size(G.INSIGHT_PAYLOAD)
        domains.append({"name": name, "bytes": n})
    char_rows = _rows(delivery, B.CHARACTER_DETAIL_SHARD_NAMES)
    loc_rows = _rows(delivery, B.LOCATION_DETAIL_SHARD_NAMES)
    return {
        "payload_bytes": encoded_size(payload),
        "insight_bytes": encoded_size(G.INSIGHT_PAYLOAD),
        "boot_bytes": encoded_size(boot),
        "search_bytes": encoded_size(search),
        "characters_bytes": encoded_size(delivery["characters"]),
        "locations_bytes": encoded_size(delivery["locations"]),
        "place_chapters_bytes": encoded_size(delivery["place-chapters"]),
        "voyages_bytes": encoded_size(delivery["voyages"]),
        "character_detail_total_bytes": sum(x["bytes"] for x in char_rows),
        "character_detail_max_bytes": char_rows[0]["bytes"],
        "character_detail_shards": char_rows,
        "location_detail_total_bytes": sum(x["bytes"] for x in loc_rows),
        "location_detail_max_bytes": loc_rows[0]["bytes"],
        "location_detail_shards": loc_rows,
        "domain_bytes": sum(x["bytes"] for x in domains),
        "domains": domains,
        "fields": fields,
    }


def human(n: int) -> str:
    return "%.2f MiB" % (n / MIB) if n >= MIB else "%.1f KiB" % (n / KIB)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="检查 V10 人物/地点可逆传输与详情分片体积")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    p = profile_payload(G.build_scope("full"))
    total = max(p["payload_bytes"], 1)
    print("最终 DATA payload：%s" % human(p["payload_bytes"]))
    print("INSIGHT payload：%s" % human(p["insight_bytes"]))
    print("V10 boot：%s · search：%s" % (human(p["boot_bytes"]), human(p["search_bytes"])))
    print("V10 人物 cards：%s；人物详情 16 shards total %s · max %s" % (
        human(p["characters_bytes"]), human(p["character_detail_total_bytes"]), human(p["character_detail_max_bytes"])))
    print("V10 地点 cards/map core：%s；地点详情 8 shards total %s · max %s" % (
        human(p["locations_bytes"]), human(p["location_detail_total_bytes"]), human(p["location_detail_max_bytes"])))
    print("V10 按章节地点：%s；航线：%s" % (human(p["place_chapters_bytes"]), human(p["voyages_bytes"])))
    print("地点详情 shard JSON 体积（大 → 小）：")
    for row in p["location_detail_shards"]:
        print("  %-24s %10s" % (row["name"], human(row["bytes"])))
    print("字段级 JSON 体积：")
    for row in p["fields"]:
        print("  %-28s %10s  %5.1f%%" % (row["key"], human(row["bytes"]), row["bytes"] * 100.0 / total))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    checks = (
        ("boot", p["boot_bytes"], BOOT_HARD), ("search", p["search_bytes"], SEARCH_HARD),
        ("characters", p["characters_bytes"], CHARACTERS_HARD),
        ("character detail max", p["character_detail_max_bytes"], CHAR_DETAIL_SHARD_HARD),
        ("character detail total", p["character_detail_total_bytes"], CHAR_DETAIL_TOTAL_HARD),
        ("locations", p["locations_bytes"], LOCATIONS_HARD),
        ("location detail max", p["location_detail_max_bytes"], LOCATION_DETAIL_SHARD_HARD),
        ("location detail total", p["location_detail_total_bytes"], LOCATION_DETAIL_TOTAL_HARD),
        ("place chapters", p["place_chapters_bytes"], PLACE_CHAPTERS_HARD),
        ("voyages", p["voyages_bytes"], VOYAGES_HARD),
    )
    failed = False
    for label, value, hard in checks:
        if value > hard:
            print("[FAIL] V10 %s: %s > %s" % (label, human(value), human(hard)))
            failed = True
    if len(p["character_detail_shards"]) != B.CHARACTER_DETAIL_SHARD_COUNT or len(p["location_detail_shards"]) != B.LOCATION_DETAIL_SHARD_COUNT:
        print("[FAIL] 详情 shard 数量异常");failed = True
    if failed:
        return 1
    print("V10 payload 分区剖析通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
