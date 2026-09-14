# -*- coding: utf-8 -*-
"""最终前端 payload 的字段级体积剖析与 V8 分区预算。

V8 在 V7 领域块之上把人物域再拆成卡片索引 + 详情补丁。搜索目录仍单独派生。
本脚本输出字段/传输分区体积，并阻止 boot、搜索或人物卡片层重新膨胀；
真实脚本与视图/实体组合 hard budget 继续由 ``check_delivery.py`` 把关。
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
CHARACTER_DETAILS_HARD = 2 * MIB


def encoded_size(value) -> int:
    """紧凑 UTF-8 JSON 字节数；与 web 数据脚本主体保持同一口径。"""
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def profile_payload(payload: dict) -> dict:
    rows = [{"key": key, "bytes": encoded_size(value)} for key, value in payload.items()]
    rows.sort(key=lambda x: (-x["bytes"], x["key"]))

    boot, chunks = B.split_web_chunks(payload)
    search = B.build_search_index(payload)
    chunk_rows = []
    for name in B.WEB_CHUNKS:
        n = encoded_size(chunks[name])
        if name == "insight":
            n += encoded_size(G.INSIGHT_PAYLOAD)
        chunk_rows.append({"name": name, "bytes": n})

    return {
        "payload_bytes": encoded_size(payload),
        "insight_bytes": encoded_size(G.INSIGHT_PAYLOAD),
        "boot_bytes": encoded_size(boot),
        "search_bytes": encoded_size(search),
        "domain_bytes": sum(row["bytes"] for row in chunk_rows),
        "domains": chunk_rows,
        "fields": rows,
    }


def human(n: int) -> str:
    return "%.2f MiB" % (n / MIB) if n >= MIB else "%.1f KiB" % (n / KIB)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="打印最终前端 payload 字段体积并检查 V8 分区预算")
    parser.add_argument("--json", type=Path, default=None, help="可选：写入机器可读 JSON")
    args = parser.parse_args(argv)

    profile = profile_payload(G.build_scope("full"))
    total = max(profile["payload_bytes"], 1)
    domains = {row["name"]: row["bytes"] for row in profile["domains"]}
    print("最终 DATA payload：%s" % human(profile["payload_bytes"]))
    print("INSIGHT payload：%s" % human(profile["insight_bytes"]))
    print("V8 boot payload：%s（hard %s）" % (human(profile["boot_bytes"]), human(BOOT_HARD)))
    print("V8 search index：%s（hard %s）" % (human(profile["search_bytes"]), human(SEARCH_HARD)))
    print("V8 人物卡片层：%s（hard %s）" % (human(domains["characters"]), human(CHARACTERS_HARD)))
    print("V8 人物详情补丁：%s（hard %s）" % (human(domains["character-details"]), human(CHARACTER_DETAILS_HARD)))
    print("V8 领域块 JSON 合计（insight 含 INSIGHT_DATA）：%s" % human(profile["domain_bytes"]))
    print("领域块 JSON 体积：")
    for row in profile["domains"]:
        print("  %-18s %10s" % (row["name"], human(row["bytes"])))
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
        ("characters cards", domains["characters"], CHARACTERS_HARD),
        ("character details", domains["character-details"], CHARACTER_DETAILS_HARD),
    ):
        if value > hard:
            print("[FAIL] V8 %s 超过 hard budget" % label)
            failed = True
    if domains["characters"] >= domains["character-details"]:
        print("[FAIL] 人物卡片层未显著轻于详情层")
        failed = True
    if failed:
        return 1
    print("V8 payload 分区剖析通过；真实脚本/视图/实体组合预算继续由 check_delivery.py 验证。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
