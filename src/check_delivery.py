# -*- coding: utf-8 -*-
"""V6 在线交付体积与结构门禁。

V5 把 DATA 拆为 boot / full；V6 再加入独立 search-index，让打开全局搜索不必下载 full。
这里同时守：HTML/首访壳、boot、搜索索引、full，以及三者的加载边界。
"""
from __future__ import annotations

import sys
from pathlib import Path

MIB = 1024 * 1024
KIB = 1024

INDEX_WARN = 48 * KIB
INDEX_HARD = 80 * KIB
SHELL_WARN = 384 * KIB
SHELL_HARD = 512 * KIB
BOOT_WARN = 64 * KIB
BOOT_HARD = 96 * KIB
SEARCH_WARN = 512 * KIB
SEARCH_HARD = 768 * KIB
FULL_WARN = int(5.5 * MIB)
FULL_HARD = 6 * MIB

REQUIRED = (
    "index.html",
    "assets/app.css",
    "assets/theme.css",
    "assets/experience.css",
    "assets/boot-data.js",
    "assets/search-index.js",
    "assets/data-full.js",
    "assets/data-loader.js",
    "assets/app.js",
    "assets/lazy-data.js",
    "assets/experience.js",
    "sw.js",
)


def human(n: int) -> str:
    return "%.2f MiB" % (n / MIB) if n >= MIB else "%.1f KiB" % (n / KIB)


def _report_budget(label: str, value: int, warn: int, hard: int) -> bool:
    if value > hard:
        print("[FAIL] %s: %s > hard %s" % (label, human(value), human(hard)))
        return False
    if value > warn:
        print("[WARN] %s: %s > warn %s" % (label, human(value), human(warn)))
    else:
        print("[OK] %s: %s" % (label, human(value)))
    return True


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0] if argv else ".ci/site")
    missing = [name for name in REQUIRED if not (root / name).exists()]
    if missing:
        print("[FAIL] web 交付缺文件：%s" % ", ".join(missing))
        return 2

    index = root / "index.html"
    boot = root / "assets" / "boot-data.js"
    search = root / "assets" / "search-index.js"
    full = root / "assets" / "data-full.js"
    index_size = index.stat().st_size
    # 首访 shell：search/full 均是按需 chunk，sw 也不参与首屏解析。
    shell_paths = [
        root / name for name in REQUIRED
        if name not in ("index.html", "assets/search-index.js", "assets/data-full.js", "sw.js")
    ]
    shell_size = index_size + sum(p.stat().st_size for p in shell_paths)

    html = index.read_text(encoding="utf-8")
    structural_errors = []
    if "const DATA=" in html:
        structural_errors.append("index.html 仍内联 DATA")
    for marker in ("THEME_SYNC_START", "EXPERIENCE_CSS_SYNC_START", "EXPERIENCE_SYNC_START"):
        if marker in html:
            structural_errors.append("index.html 仍内联生成镜像：%s" % marker)
    for asset in (
        "assets/app.css", "assets/theme.css", "assets/experience.css",
        "assets/boot-data.js", "assets/data-loader.js", "assets/app.js",
        "assets/lazy-data.js", "assets/experience.js",
    ):
        if asset not in html:
            structural_errors.append("index.html 未引用 %s" % asset)
    for lazy_asset in ("assets/search-index.js", "assets/data-full.js"):
        if lazy_asset in html:
            structural_errors.append("index.html 直接引用 %s，按需加载边界失效" % lazy_asset)
    if (root / "assets" / "data.js").exists():
        structural_errors.append("仍生成旧 assets/data.js，可能回退到 V4 全量首访")

    passed = True
    for label, value, warn, hard in (
        ("online index", index_size, INDEX_WARN, INDEX_HARD),
        ("online first-load shell", shell_size, SHELL_WARN, SHELL_HARD),
        ("boot-data.js", boot.stat().st_size, BOOT_WARN, BOOT_HARD),
        ("lazy search-index.js", search.stat().st_size, SEARCH_WARN, SEARCH_HARD),
        ("lazy data-full.js", full.stat().st_size, FULL_WARN, FULL_HARD),
    ):
        passed = _report_budget(label, value, warn, hard) and passed

    for msg in structural_errors:
        print("[FAIL] %s" % msg)
        passed = False
    if not passed:
        return 1
    print("V6 在线 boot/search/full 按需交付结构与体积预算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
