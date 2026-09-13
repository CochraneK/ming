# -*- coding: utf-8 -*-
"""最终前端 payload 的字段级体积剖析与 V5 预算工具。

V4 已把在线 HTML 与 DATA 拆开，但 ``assets/data.js`` 仍是首访最大资源。V5 在拆包前
先把最终模型按顶层字段量化，避免凭感觉分块；后续 lazy chunk 的预算也继续由本文件守。

用法：
    python src/check_payload_budget.py
    python src/check_payload_budget.py --json .ci/payload-sizes.json

当前阶段只做事实测量，不因为业务数据自然增长阻塞 CI。V5 完成分块后会在这里加入
boot / chunk 的 hard budget。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_report as G  # noqa: E402


def encoded_size(value) -> int:
    """与 web data.js 相同口径：紧凑 UTF-8 JSON 字节数。"""
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def profile_payload(payload: dict) -> dict:
    rows = []
    for key, value in payload.items():
        rows.append({"key": key, "bytes": encoded_size(value)})
    rows.sort(key=lambda x: (-x["bytes"], x["key"]))
    return {
        "payload_bytes": encoded_size(payload),
        "insight_bytes": encoded_size(G.INSIGHT_PAYLOAD),
        "fields": rows,
    }


def human(n: int) -> str:
    return "%.2f MiB" % (n / 1048576) if n >= 1048576 else "%.1f KiB" % (n / 1024)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="打印最终前端 payload 的字段级体积")
    parser.add_argument("--json", type=Path, default=None, help="可选：写入机器可读 JSON")
    args = parser.parse_args(argv)

    profile = profile_payload(G.build_scope("full"))
    total = max(profile["payload_bytes"], 1)
    print("最终 DATA payload：%s" % human(profile["payload_bytes"]))
    print("INSIGHT payload：%s" % human(profile["insight_bytes"]))
    print("字段级 JSON 体积：")
    for row in profile["fields"]:
        pct = row["bytes"] * 100.0 / total
        print("  %-28s %10s  %5.1f%%" % (row["key"], human(row["bytes"]), pct))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
