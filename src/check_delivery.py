# -*- coding: utf-8 -*-
"""V10 在线交付结构、人物/地点详情 shard 与首次传输预算门禁。"""
from __future__ import annotations

import sys
from pathlib import Path

import build as B

MIB = 1024 * 1024
KIB = 1024
INDEX_WARN, INDEX_HARD = 48 * KIB, 80 * KIB
SHELL_WARN, SHELL_HARD = 384 * KIB, 512 * KIB
BOOT_WARN, BOOT_HARD = 72 * KIB, 112 * KIB
SEARCH_WARN, SEARCH_HARD = 512 * KIB, 768 * KIB
CHAR_DETAIL_WARN, CHAR_DETAIL_HARD = 128 * KIB, 192 * KIB
LOC_DETAIL_WARN, LOC_DETAIL_HARD = 96 * KIB, 128 * KIB

CHUNK_BUDGETS = {
    "characters": (700 * KIB, 1024 * KIB),
    **{name: (CHAR_DETAIL_WARN, CHAR_DETAIL_HARD) for name in B.CHARACTER_DETAIL_SHARD_NAMES},
    "locations": (400 * KIB, 512 * KIB),
    **{name: (LOC_DETAIL_WARN, LOC_DETAIL_HARD) for name in B.LOCATION_DETAIL_SHARD_NAMES},
    "place-chapters": (240 * KIB, 320 * KIB),
    "voyages": (32 * KIB, 64 * KIB),
    "events": (450 * KIB, 512 * KIB),
    "relations": (800 * KIB, 900 * KIB),
    "time": (500 * KIB, 600 * KIB),
    "graphs": (800 * KIB, 900 * KIB),
    "insight": (220 * KIB, 256 * KIB),
    "meta": (130 * KIB, 160 * KIB),
}
VIEW_CHUNKS = {
    "overview": (), "distribution": (),
    "visuals": ("graphs",),
    "locations": ("locations",),
    "map": ("locations",),
    "characters": ("characters",),
    "events": ("events",),
    "relations": ("relations",),
    "timeline": ("time", "events"),
    "dynasty": ("time", "events"),
    "chronicle": ("time", "characters"),
    "insight": ("insight",),
}
VIEW_WARN, VIEW_HARD = int(1.1 * MIB), int(1.5 * MIB)
PERSON_WARN, PERSON_HARD = int(1.1 * MIB), int(1.35 * MIB)
PLACE_WARN, PLACE_HARD = 1024 * KIB, int(1.25 * MIB)
EVENT_WARN, EVENT_HARD = 1024 * KIB, int(1.25 * MIB)

REQUIRED_BASE = (
    "index.html", "assets/app.css", "assets/theme.css", "assets/experience.css",
    "assets/boot-data.js", "assets/search-index.js", "assets/data-loader.js",
    "assets/app.js", "assets/lazy-data.js", "assets/experience.js", "sw.js",
)
REQUIRED_CHUNKS = tuple("assets/data-%s.js" % name for name in B.WEB_DELIVERY_CHUNKS)
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
    shell_names = [name for name in REQUIRED_BASE if name not in ("index.html", "assets/search-index.js", "sw.js")]
    shell_size = index_size + sum((root / name).stat().st_size for name in shell_names)
    chunk_sizes = {name: (root / "assets" / ("data-%s.js" % name)).stat().st_size for name in B.WEB_DELIVERY_CHUNKS}
    char_detail = {name: chunk_sizes[name] for name in B.CHARACTER_DETAIL_SHARD_NAMES}
    loc_detail = {name: chunk_sizes[name] for name in B.LOCATION_DETAIL_SHARD_NAMES}

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
    for obsolete in ("assets/data.js", "assets/data-full.js", "assets/data-character-details.js", "assets/data-space.js", "assets/data-location-details.js"):
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

    max_char_name = max(char_detail, key=char_detail.get);max_char = char_detail[max_char_name]
    max_loc_name = max(loc_detail, key=loc_detail.get);max_loc = loc_detail[max_loc_name]
    total_char = sum(char_detail.values());total_loc = sum(loc_detail.values())
    print("人物详情分片：%d shards · total %s · max %s=%s" % (len(char_detail), human(total_char), max_char_name, human(max_char)))
    print("地点详情分片：%d shards · total %s · max %s=%s" % (len(loc_detail), human(total_loc), max_loc_name, human(max_loc)))

    print("视图首次数据传输（不计已缓存块）：")
    for view, chunks in VIEW_CHUNKS.items():
        size = sum(chunk_sizes[name] for name in chunks)
        passed = _report_budget("  view %s [%s]" % (view, "+".join(chunks) or "boot"), size, VIEW_WARN, VIEW_HARD) and passed
    chapter_mode = chunk_sizes["locations"] + chunk_sizes["place-chapters"]
    voyage_mode = chunk_sizes["locations"] + chunk_sizes["voyages"] + chunk_sizes["events"]
    passed = _report_budget("  location chapter mode [locations+place-chapters]", chapter_mode, 700*KIB, 900*KIB) and passed
    passed = _report_budget("  map voyage mode [locations+voyages+events]", voyage_mode, 900*KIB, int(1.15*MIB)) and passed

    person_size = chunk_sizes["characters"] + max_char + chunk_sizes["events"] + chunk_sizes["insight"]
    place_size = chunk_sizes["locations"] + max_loc + chunk_sizes["events"] + chunk_sizes["insight"]
    event_size = chunk_sizes["events"] + chunk_sizes["locations"] + chunk_sizes["insight"]
    print("实体详情首次数据传输（零缓存；详情按最大 shard 计）：")
    passed = _report_budget("  entity person", person_size, PERSON_WARN, PERSON_HARD) and passed
    passed = _report_budget("  entity place", place_size, PLACE_WARN, PLACE_HARD) and passed
    passed = _report_budget("  entity event", event_size, EVENT_WARN, EVENT_HARD) and passed

    if chunk_sizes["characters"] + chunk_sizes["time"] >= int(1.5 * MIB):
        structural_errors.append("年谱 characters+time 未保持在 1.5 MiB 以下")
    if chunk_sizes["locations"] >= 512 * KIB:
        structural_errors.append("地点摘要未降到 512 KiB 以下")
    if max_loc >= 128 * KIB:
        structural_errors.append("最大地点详情 shard 达到 128 KiB hard limit")
    if place_size >= int(1.25 * MIB):
        structural_errors.append("地点零缓存详情入口未降到 1.25 MiB 以下")
    if event_size >= int(1.25 * MIB):
        structural_errors.append("事件零缓存详情入口未降到 1.25 MiB 以下")
    if total_loc >= 768 * KIB:
        structural_errors.append("地点详情 shards 总体积超过 768 KiB")

    for msg in structural_errors:
        print("[FAIL] %s" % msg);passed = False
    if not passed:
        return 1
    print("V10 在线人物/地点摘要、详情 shards 与模式级按需交付预算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
