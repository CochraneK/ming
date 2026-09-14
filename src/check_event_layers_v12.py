# -*- coding: utf-8 -*-
"""V12 事件摘要 / 详情分片与关键入口预算门禁。"""
from __future__ import annotations

import sys
from pathlib import Path

import split_event_asset_v12 as V12
import split_time_asset_v11 as V11

KIB = 1024
MIB = 1024 * 1024
EVENT_CORE_WARN, EVENT_CORE_HARD = 260 * KIB, 320 * KIB
EVENT_SHARD_WARN, EVENT_SHARD_HARD = 48 * KIB, 96 * KIB
EVENT_DETAIL_TOTAL_HARD = 384 * KIB
TIME_ONLY_HARD = 450 * KIB
PERSON_HARD = 800 * KIB
PLACE_HARD = 1024 * KIB
EVENT_ENTITY_HARD = 1024 * KIB
VOYAGE_HARD = 450 * KIB


def human(n: int) -> str:
    return "%.2f MiB" % (n / MIB) if n >= MIB else "%.1f KiB" % (n / KIB)


def report(label: str, value: int, warn: int, hard: int) -> bool:
    if value > hard:
        print("[FAIL] %s: %s > hard %s" % (label, human(value), human(hard)));return False
    if value > warn: print("[WARN] %s: %s > warn %s" % (label, human(value), human(warn)))
    else: print("[OK] %s: %s" % (label, human(value)))
    return True


def _size(root: Path, name: str) -> int:
    path = root / "assets" / name
    if not path.exists(): raise RuntimeError("缺少 %s" % path)
    return path.stat().st_size


def _max_glob(root: Path, pattern: str) -> tuple[str, int]:
    paths = list((root / "assets").glob(pattern))
    if not paths: raise RuntimeError("没有匹配 %s" % pattern)
    path = max(paths, key=lambda p:p.stat().st_size)
    return path.name, path.stat().st_size


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0] if argv else ".ci/site")
    try:
        event_stats = V12.check_site(root)
        time_stats = V11.check_site(root)
        characters = _size(root, "data-characters.js")
        locations = _size(root, "data-locations.js")
        insight = _size(root, "data-insight.js")
        voyages = _size(root, "data-voyages.js")
        char_name, char_max = _max_glob(root, "data-character-detail-*.js")
        loc_name, loc_max = _max_glob(root, "data-location-detail-*.js")
    except RuntimeError as exc:
        print("[FAIL] %s" % exc);return 2

    event_core = event_stats["events_bytes"]
    event_max = event_stats["detail_max_bytes"]
    event_total = event_stats["detail_total_bytes"]
    time_only = time_stats["time_bytes"]
    person = characters + char_max + insight
    place = locations + loc_max + event_core + insight
    event_entity = event_core + event_max + locations + insight
    voyage = locations + voyages

    passed = True
    passed = report("event core", event_core, EVENT_CORE_WARN, EVENT_CORE_HARD) and passed
    passed = report("event detail max %s" % event_stats["detail_max_name"], event_max, EVENT_SHARD_WARN, EVENT_SHARD_HARD) and passed
    passed = report("event details total", event_total, 300 * KIB, EVENT_DETAIL_TOTAL_HARD) and passed
    passed = report("timeline/dynasty [time only]", time_only, 420 * KIB, TIME_ONLY_HARD) and passed
    passed = report("person detail [characters+max-char+insight]", person, 740 * KIB, PERSON_HARD) and passed
    passed = report("place detail [locations+max-place+event-core+insight]", place, 900 * KIB, PLACE_HARD) and passed
    passed = report("event detail [event-core+max-event+locations+insight]", event_entity, 900 * KIB, EVENT_ENTITY_HARD) and passed
    passed = report("voyage zero-cache [locations+voyages]", voyage, 400 * KIB, VOYAGE_HARD) and passed

    loader = (root / "assets" / "data-loader.js").read_text(encoding="utf-8")
    structural = []
    for token in (
        "timeline:['time']", "dynasty:['time']", "events:['events']",
        "EVENT_DETAIL_SHARD_COUNT=8", "__MING_EVENT_DETAILS__", "eventDetailChunkFor",
    ):
        if token not in loader: structural.append("loader 缺少 %s" % token)
    if "timeline:['time','events']" in loader or "dynasty:['time','events']" in loader:
        structural.append("时间视图仍预取 events")
    if event_stats["event_count"] != 1106:
        structural.append("事件摘要数量异常：%d" % event_stats["event_count"])
    if len(event_stats["detail_sizes"]) != 8:
        structural.append("事件详情 shard 数量异常")
    for msg in structural:
        print("[FAIL] %s" % msg);passed=False

    print("V12 组合：char max=%s %s · place max=%s %s" % (char_name,human(char_max),loc_name,human(loc_max)))
    if not passed:return 1
    print("V12 事件摘要/详情分片与延迟事件入口预算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
