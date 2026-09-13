# -*- coding: utf-8 -*-
"""V4 在线交付体积与结构门禁。

在线版应该是一个很小的 HTML 壳，重数据放在 assets/data.js，样式与脚本可被浏览器
独立缓存。这里守的是“交付结构”，不是业务数据规模；业务总体积仍由 check_budget.py 守。
"""
from __future__ import annotations

import sys
from pathlib import Path

MIB = 1024 * 1024
KIB = 1024

# HTML 壳一旦重新膨胀到几十/几百 KB，通常意味着有人把镜像或数据重新内联回去了。
INDEX_WARN = 48 * KIB
INDEX_HARD = 80 * KIB
SHELL_WARN = 320 * KIB
SHELL_HARD = 512 * KIB

REQUIRED = (
    "index.html",
    "assets/app.css",
    "assets/theme.css",
    "assets/experience.css",
    "assets/data.js",
    "assets/app.js",
    "assets/experience.js",
    "sw.js",
)


def human(n: int) -> str:
    return "%.2f MiB" % (n / MIB) if n >= MIB else "%.1f KiB" % (n / KIB)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0] if argv else ".ci/site")
    missing = [name for name in REQUIRED if not (root / name).exists()]
    if missing:
        print("[FAIL] web 交付缺文件：%s" % ", ".join(missing))
        return 2

    index = root / "index.html"
    data = root / "assets" / "data.js"
    index_size = index.stat().st_size
    shell_paths = [root / name for name in REQUIRED if name not in ("index.html", "assets/data.js")]
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
        "assets/data.js", "assets/app.js", "assets/experience.js",
    ):
        if asset not in html:
            structural_errors.append("index.html 未引用 %s" % asset)

    failed = False
    for label, value, warn, hard in (
        ("online index", index_size, INDEX_WARN, INDEX_HARD),
        ("online shell(no data.js)", shell_size, SHELL_WARN, SHELL_HARD),
    ):
        if value > hard:
            print("[FAIL] %s: %s > hard %s" % (label, human(value), human(hard)))
            failed = True
        elif value > warn:
            print("[WARN] %s: %s > warn %s" % (label, human(value), human(warn)))
        else:
            print("[OK] %s: %s" % (label, human(value)))

    print("[OK] separated data.js: %s" % human(data.stat().st_size))
    for msg in structural_errors:
        print("[FAIL] %s" % msg)
        failed = True
    if failed:
        return 1
    print("在线交付结构与体积预算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
