# -*- coding: utf-8 -*-
"""V11 时间域物理分层交付门禁。"""
from __future__ import annotations

import sys
from pathlib import Path

import split_time_asset_v11 as V11

KIB = 1024
LIFESPANS_HARD = 64 * KIB
TIME_HARD = 512 * KIB
CHRONICLE_WARN = 470 * KIB
CHRONICLE_HARD = 512 * KIB


def human(n: int) -> str:
    return "%.1f KiB" % (n / KIB)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0] if argv else ".ci/site")
    try:
        stats = V11.check_site(root)
    except (RuntimeError, ValueError) as exc:
        print("[FAIL] %s" % exc)
        return 2

    assets = root / "assets"
    loader_path = assets / "data-loader.js"
    characters_path = assets / "data-characters.js"
    if not loader_path.exists() or not characters_path.exists():
        print("[FAIL] 缺少 loader 或 characters 产物")
        return 2
    loader = loader_path.read_text(encoding="utf-8")
    errors = []
    for token in (
        "'time','lifespans','graphs'",
        "timeline:['time','events']",
        "dynasty:['time','events']",
        "chronicle:['lifespans','characters']",
    ):
        if token not in loader:
            errors.append("loader 缺少 V11 路由：%s" % token)
    if "chronicle:['time','characters']" in loader:
        errors.append("年谱仍绑定整块 time")

    time_size = stats["time_bytes"]
    life_size = stats["lifespans_bytes"]
    chronicle_size = characters_path.stat().st_size + life_size
    print("V11 time（不含 lifespans）：%s" % human(time_size))
    print("V11 lifespans：%s · %d 人" % (human(life_size), stats["lifespans_count"]))
    print("V11 年谱零缓存数据：characters + lifespans = %s" % human(chronicle_size))

    if time_size > TIME_HARD:
        errors.append("data-time.js 超过 %s" % human(TIME_HARD))
    if life_size > LIFESPANS_HARD:
        errors.append("data-lifespans.js 超过 %s" % human(LIFESPANS_HARD))
    if chronicle_size > CHRONICLE_HARD:
        errors.append("年谱入口超过 hard %s" % human(CHRONICLE_HARD))
    elif chronicle_size > CHRONICLE_WARN:
        print("[WARN] 年谱入口 %s > warn %s" % (human(chronicle_size), human(CHRONICLE_WARN)))

    if errors:
        for error in errors:
            print("[FAIL] %s" % error)
        return 1
    print("V11 时间域分层与年谱预算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
