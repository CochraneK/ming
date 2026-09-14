# -*- coding: utf-8 -*-
"""最终前端 payload 的字段级体积剖析与 V9 详情分片预算。

V9 在 V8 人物卡片/详情二级传输之上，将详情补丁按姓名确定性散列为 16 个物理 shard。
本脚本同时观察逻辑详情总量、每个 shard 的大小与最大 shard，避免为了减少单次请求而
引入异常膨胀；真实 JS 文件与视图/实体组合 hard budget 继续由 check_delivery.py 把关。
"""
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
DETAIL_SHARD_HARD = 192 * KIB
DETAIL_TOTAL_HARD = 2 * MIB


def encoded_size(value) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def profile_payload(payload: dict) -> dict:
    rows = [{"key": key, "bytes": encoded_size(value)} for key, value in payload.items()]
    rows.sort(key=lambda x: (-x["bytes"], x["key"]))

    boot, logical = B.split_web_chunks(payload)
    delivery = B.split_delivery_chunks(logical)
    search = B.build_search_index(payload)

    domain_rows = []
    for name in B.WEB_DELIVERY_CHUNKS:
        n = encoded_size(delivery[name])
        if name == "insight":
            n += encoded_size(G.INSIGHT_PAYLOAD)
        domain_rows.append({"name": name, "bytes": n})

    detail_rows = [
        {"name": name, "bytes": encoded_size(delivery[name])}
        for name in B.CHARACTER_DETAIL_SHARD_NAMES
    ]
    detail_rows.sort(key=lambda x: (-x["bytes"], x["name"]))

    return {
        "payload_bytes": encoded_size(payload),
        "insight_bytes": encoded_size(G.INSIGHT_PAYLOAD),
        "boot_bytes": encoded_size(boot),
        "search_bytes": encoded_size(search),
        "characters_bytes": encoded_size(delivery["characters"]),
        "detail_total_bytes": sum(row["bytes"] for row in detail_rows),
        "detail_max_bytes": detail_rows[0]["bytes"] if detail_rows else 0,
        "detail_min_bytes": detail_rows[-1]["bytes"] if detail_rows else 0,
        "detail_shards": detail_rows,
        "domain_bytes": sum(row["bytes"] for row in domain_rows),
        "domains": domain_rows,
        "fields": rows,
    }


def human(n: int) -> str:
    return "%.2f MiB" % (n / MIB) if n >= MIB else "%.1f KiB" % (n / KIB)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="打印最终前端 payload 字段体积并检查 V9 人物详情分片预算")
    parser.add_argument("--json", type=Path, default=None, help="可选：写入机器可读 JSON")
    args = parser.parse_args(argv)

    profile = profile_payload(G.build_scope("full"))
    total = max(profile["payload_bytes"], 1)
    print("最终 DATA payload：%s" % human(profile["payload_bytes"]))
    print("INSIGHT payload：%s" % human(profile["insight_bytes"]))
    print("V9 boot payload：%s（hard %s）" % (human(profile["boot_bytes"]), human(BOOT_HARD)))
    print("V9 search index：%s（hard %s）" % (human(profile["search_bytes"]), human(SEARCH_HARD)))
    print("V9 人物卡片层：%s（hard %s）" % (human(profile["characters_bytes"]), human(CHARACTERS_HARD)))
    print("V9 人物详情 shards：%d 个 · total %s（hard %s）· max %s（hard %s）· min %s" % (
        len(profile["detail_shards"]), human(profile["detail_total_bytes"]), human(DETAIL_TOTAL_HARD),
        human(profile["detail_max_bytes"]), human(DETAIL_SHARD_HARD), human(profile["detail_min_bytes"]),
    ))
    print("V9 物理领域块 JSON 合计（insight 含 INSIGHT_DATA）：%s" % human(profile["domain_bytes"]))
    print("人物详情 shard JSON 体积（大 → 小）：")
    for row in profile["detail_shards"]:
        print("  %-24s %10s" % (row["name"], human(row["bytes"])))
    print("字段级 JSON 体积：")
    for row in profile["fields"]:
        pct = row["bytes"] * 100.0 / total
        print("  %-28s %10s  %5.1f%%" % (row["key"], human(row["bytes"]), pct))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = False
    for label, value, hard in (
        ("boot payload", profile["boot_bytes"], BOOT_HARD),
        ("search index", profile["search_bytes"], SEARCH_HARD),
        ("characters cards", profile["characters_bytes"], CHARACTERS_HARD),
        ("detail shard max", profile["detail_max_bytes"], DETAIL_SHARD_HARD),
        ("detail shards total", profile["detail_total_bytes"], DETAIL_TOTAL_HARD),
    ):
        if value > hard:
            print("[FAIL] V9 %s 超过 hard budget" % label)
            failed = True
    if len(profile["detail_shards"]) != B.CHARACTER_DETAIL_SHARD_COUNT:
        print("[FAIL] 人物详情 shard 数量异常")
        failed = True
    if profile["detail_max_bytes"] >= profile["characters_bytes"]:
        print("[FAIL] 最大详情 shard 不应达到人物卡片层大小")
        failed = True
    if failed:
        return 1
    print("V9 payload 分区剖析通过；真实脚本/视图/实体组合预算继续由 check_delivery.py 验证。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
