# -*- coding: utf-8 -*-
"""轻量前端体积预算。

目标不是追求极限压缩，而是防止静态报告在无人察觉时持续膨胀。
- warn：提醒复查，但不阻塞 CI；
- hard：明显异常时阻塞 CI。
"""
from __future__ import annotations

import argparse
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024
KIB = 1024

BUDGETS = {
    "standalone": (5.6 * MIB, 6.5 * MIB),
    "app.js": (140 * KIB, 175 * KIB),
    "base+theme+experience.css": (64 * KIB, 84 * KIB),
    "experience.js": (20 * KIB, 28 * KIB),
}


def fmt(n: int) -> str:
    return f"{n / MIB:.2f} MiB" if n >= MIB else f"{n / KIB:.1f} KiB"


def evaluate(name: str, size: int) -> tuple[str, str]:
    warn, hard = BUDGETS[name]
    if size > hard:
        return "ERROR", f"{name}: {fmt(size)} > hard {fmt(int(hard))}"
    if size > warn:
        return "WARNING", f"{name}: {fmt(size)} > warn {fmt(int(warn))}"
    return "OK", f"{name}: {fmt(size)}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="检查 Ming 静态前端体积预算")
    p.add_argument("standalone", nargs="?", default="index.html")
    args = p.parse_args(argv)
    report = Path(args.standalone)
    if not report.exists():
        raise SystemExit(f"standalone 不存在：{report}")

    css_paths = [BASE / "web/css/app.css", BASE / "web/css/theme.css", BASE / "web/css/experience.css"]
    sizes = {
        "standalone": report.stat().st_size,
        "app.js": (BASE / "web/js/app.js").stat().st_size,
        "base+theme+experience.css": sum(p.stat().st_size for p in css_paths),
        "experience.js": (BASE / "web/js/experience.js").stat().st_size,
    }
    errors = 0
    for name, size in sizes.items():
        level, msg = evaluate(name, size)
        print(f"[{level}] {msg}")
        errors += level == "ERROR"
    if errors:
        print("体积预算失败：先确认是否为必要增长，再调整阈值或拆分在线产物。")
        return 1
    print("体积预算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
