# -*- coding: utf-8 -*-
"""V8 在线交付结构、领域块、人物详情补丁与视图传输预算门禁。"""
from __future__ import annotations

import sys
from pathlib import Path

MIB = 1024 * 1024
KIB = 1024
INDEX_WARN, INDEX_HARD = 48 * KIB, 80 * KIB
SHELL_WARN, SHELL_HARD = 384 * KIB, 512 * KIB
BOOT_WARN, BOOT_HARD = 72 * KIB, 112 * KIB
SEARCH_WARN, SEARCH_HARD = 512 * KIB, 768 * KIB

CHUNK_BUDGETS = {
    "characters": (700 * KIB, 1024 * KIB),
    "character-details": (int(1.5 * MIB), 2 * MIB),
    "events": (450 * KIB, 512 * KIB),
    "space": (1024 * KIB, int(1.15 * MIB)),
    "relations": (800 * KIB, 900 * KIB),
    "time": (500 * KIB, 600 * KIB),
    "graphs": (800 * KIB, 900 * KIB),
    "insight": (220 * KIB, 256 * KIB),
    "meta": (130 * KIB, 160 * KIB),
}
VIEW_CHUNKS = {
    "overview": (), "distribution": (),
    "visuals": ("graphs",),
    "locations": ("space", "events", "insight"),
    "map": ("space", "events"),
    "characters": ("characters",),
    "events": ("events",),
    "relations": ("relations",),
    "timeline": ("time", "events"),
    "dynasty": ("time", "events"),
    "chronicle": ("time", "characters"),
    "insight": ("insight",),
}
ENTITY_CHUNKS = {
    "person": ("characters", "character-details", "events", "insight"),
    "place": ("space", "events", "insight"),
    "event": ("events", "space", "insight"),
}
VIEW_WARN, VIEW_HARD = int(1.5 * MIB), 2 * MIB
ENTITY_WARN, ENTITY_HARD = int(2.75 * MIB), int(3.25 * MIB)

REQUIRED_BASE = (
    "index.html", "assets/app.css", "assets/theme.css", "assets/experience.css",
    "assets/boot-data.js", "assets/search-index.js", "assets/data-loader.js",
    "assets/app.js", "assets/lazy-data.js", "assets/experience.js", "sw.js",
)
REQUIRED_CHUNKS = tuple("assets/data-%s.js" % name for name in CHUNK_BUDGETS)
REQUIRED = REQUIRED_BASE + REQUIRED_CHUNKS


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
    index_size = index.stat().st_size
    # 首访 shell 不含 search / 领域块 / sw。
    shell_names = [
        name for name in REQUIRED_BASE
        if name not in ("index.html", "assets/search-index.js", "sw.js")
    ]
    shell_size = index_size + sum((root / name).stat().st_size for name in shell_names)
    chunk_sizes = {name: (root / "assets" / ("data-%s.js" % name)).stat().st_size for name in CHUNK_BUDGETS}

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
    for lazy_asset in ("assets/search-index.js",) + REQUIRED_CHUNKS:
        if lazy_asset in html:
            structural_errors.append("index.html 直接引用 %s，按需边界失效" % lazy_asset)
    for obsolete in ("assets/data.js", "assets/data-full.js"):
        if (root / obsolete).exists():
            structural_errors.append("仍生成旧 %s" % obsolete)

    passed = True
    for label, value, warn, hard in (
        ("online index", index_size, INDEX_WARN, INDEX_HARD),
        ("online first-load shell", shell_size, SHELL_WARN, SHELL_HARD),
        ("boot-data.js", boot.stat().st_size, BOOT_WARN, BOOT_HARD),
        ("lazy search-index.js", search.stat().st_size, SEARCH_WARN, SEARCH_HARD),
    ):
        passed = _report_budget(label, value, warn, hard) and passed

    for name, (warn, hard) in CHUNK_BUDGETS.items():
        passed = _report_budget("domain %s" % name, chunk_sizes[name], warn, hard) and passed

    print("视图首次数据传输（不计已缓存块）：")
    for view, chunks in VIEW_CHUNKS.items():
        size = sum(chunk_sizes[name] for name in chunks)
        passed = _report_budget("  view %s [%s]" % (view, "+".join(chunks) or "boot"), size, VIEW_WARN, VIEW_HARD) and passed

    print("实体详情首次数据传输（最坏按零缓存计）：")
    for kind, chunks in ENTITY_CHUNKS.items():
        size = sum(chunk_sizes[name] for name in chunks)
        passed = _report_budget("  entity %s [%s]" % (kind, "+".join(chunks)), size, ENTITY_WARN, ENTITY_HARD) and passed

    # V8 的核心收益必须由门禁固定住：人物索引必须显著小于详情补丁，年谱不得再逼近 V7 的 2.20 MiB。
    if chunk_sizes["characters"] >= chunk_sizes["character-details"]:
        structural_errors.append("人物卡片 chunk 未小于详情补丁，V8 分层失去意义")
    if chunk_sizes["characters"] + chunk_sizes["time"] >= int(1.5 * MIB):
        structural_errors.append("年谱 characters+time 未降到 1.5 MiB 以下")

    for msg in structural_errors:
        print("[FAIL] %s" % msg);passed = False
    if not passed:
        return 1
    print("V8 在线 boot/search/domain/character-details 交付结构与体积预算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
