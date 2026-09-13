# -*- coding: utf-8 -*-
"""最终前端 payload 的字段级体积剖析与 V5 boot/full 预算。

V4 已把在线 HTML 与 DATA 拆开；V5 再把最终模型拆为 boot 首屏与 full 深度数据。
本文件同时输出字段占比，并阻止 boot 因误塞重字段重新膨胀。
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
BOOT_HARD = 96 * KIB
FULL_HARD = 6 * MIB


def encoded_size(value) -> int:
    """与 V5 web chunks 相同口径：紧凑 UTF-8 JSON 字节数。"""
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def profile_payload(payload: dict) -> dict:
    rows = []
    for key, value in payload.items():
        rows.append({"key": key, "bytes": encoded_size(value)})
    rows.sort(key=lambda x: (-x["bytes"], x["key"]))
    boot, full = B.split_web_payload(payload)
    return {
        "payload_bytes": encoded_size(payload),
        "insight_bytes": encoded_size(G.INSIGHT_PAYLOAD),
        "boot_bytes": encoded_size(boot),
        "full_bytes": encoded_size(full) + encoded_size(G.INSIGHT_PAYLOAD),
        "fields": rows,
    }


def human(n: int) -> str:
    return "%.2f MiB" % (n / MIB) if n >= MIB else "%.1f KiB" % (n / KIB)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="打印最终前端 payload 字段体积并检查 V5 分块预算")
    parser.add_argument("--json", type=Path, default=None, help="可选：写入机器可读 JSON")
    args = parser.parse_args(argv)

    profile = profile_payload(G.build_scope("full"))
    total = max(profile["payload_bytes"], 1)
    print("最终 DATA payload：%s" % human(profile["payload_bytes"]))
    print("INSIGHT payload：%s" % human(profile["insight_bytes"]))
    print("V5 boot payload：%s（hard %s）" % (human(profile["boot_bytes"]), human(BOOT_HARD)))
    print("V5 lazy full+insight：%s（hard %s）" % (human(profile["full_bytes"]), human(FULL_HARD)))
    print("字段级 JSON 体积：")
    for row in profile["fields"]:
        pct = row["bytes"] * 100.0 / total
        print("  %-28s %10s  %5.1f%%" % (row["key"], human(row["bytes"]), pct))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = False
    if profile["boot_bytes"] > BOOT_HARD:
        print("[FAIL] V5 boot payload 超过 hard budget")
        failed = True
    if profile["full_bytes"] > FULL_HARD:
        print("[FAIL] V5 full payload 超过 hard budget")
        failed = True
    if failed:
        return 1
    print("V5 payload 分块预算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
