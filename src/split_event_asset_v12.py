# -*- coding: utf-8 -*-
"""V12 在线事件物理分层：轻量 events 核心 + 8 个确定性详情 shard。

最终 DATA、generate_report 与 standalone 完全不变。该脚本只处理已经构建好的 web 产物：
- data-events.js 保留事件索引、人物/地点上下文与搜索所需摘要；
- year_source/year_approx/year_note/year_start/year_end/sources 等完整详情进入 shard；
- 8 个 shard 按事件稳定 id 做 DJB2-xor 散列；
- 首次拆分时逐值重建原始 events，保证传输变换无损；重复运行则做结构校验。
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

EVENT_DETAIL_SHARD_COUNT = 8
EVENT_DETAIL_SHARD_NAMES = tuple("event-detail-%02d" % i for i in range(EVENT_DETAIL_SHARD_COUNT))
EVENT_CARD_KEYS = ("id", "type", "name", "year", "category", "location", "participants")
_ASSIGN_RE = re.compile(r"^Object\.assign\(DATA,(.*)\);$", re.MULTILINE)


def _compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _stable_index(value: str, count: int) -> int:
    h = 5381
    for ch in str(value or ""):
        h = ((h * 33) ^ ord(ch)) & 0xFFFFFFFF
    return h % count


def event_detail_shard_name(event_id: str) -> str:
    return "event-detail-%02d" % _stable_index(event_id, EVENT_DETAIL_SHARD_COUNT)


def read_chunk_payload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = _ASSIGN_RE.search(text)
    if not match:
        raise RuntimeError("找不到 Object.assign(DATA,...)：%s" % path)
    value = json.loads(match.group(1))
    if not isinstance(value, dict):
        raise RuntimeError("DATA chunk 不是对象：%s" % path)
    return value


def _replace_payload(text: str, payload: dict) -> str:
    updated, count = _ASSIGN_RE.subn("Object.assign(DATA,%s);" % _compact(payload), text, count=1)
    if count != 1:
        raise RuntimeError("替换 events DATA chunk 失败")
    return updated


def split_event_transport(events: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    summaries = []
    details = {}
    for event in events:
        event_id = str(event.get("id") or "")
        if not event_id:
            raise RuntimeError("V12 事件详情拆分遇到空 id")
        summary = {key: copy.deepcopy(event[key]) for key in EVENT_CARD_KEYS if key in event}
        summary["sourceCount"] = len(event.get("sources") or [])
        detail = {
            key: copy.deepcopy(value)
            for key, value in event.items()
            if key not in summary or summary.get(key) != value
        }
        summaries.append(summary)
        details[event_id] = detail
    return summaries, details


def split_detail_shards(details: dict[str, dict]) -> dict[str, dict]:
    shards = {name: {"details": {}} for name in EVENT_DETAIL_SHARD_NAMES}
    for event_id, patch in details.items():
        shards[event_detail_shard_name(event_id)]["details"][event_id] = copy.deepcopy(patch)
    return shards


def reconstruct_events(summaries: list[dict], details: dict[str, dict]) -> list[dict]:
    result = []
    for summary in summaries:
        item = copy.deepcopy(summary)
        event_id = item.get("id")
        item.pop("sourceCount", None)
        item.update(copy.deepcopy(details.get(event_id, {})))
        result.append(item)
    return result


def _detail_script(name: str, data: dict) -> str:
    return (
        "window.__MING_EVENT_DETAILS__=Object.assign(window.__MING_EVENT_DETAILS__||{},%s);\n"
        "if(window.__MING_APPLY_EVENT_DETAILS__)window.__MING_APPLY_EVENT_DETAILS__();\n"
        "window.__MING_DATA_CHUNKS__=window.__MING_DATA_CHUNKS__||{};\n"
        "window.__MING_DATA_CHUNKS__[%s]=true;\n"
        "document.dispatchEvent(new CustomEvent('ming:data-chunk',{detail:{name:%s}}));\n"
        % (_compact(data.get("details") or {}), json.dumps(name), json.dumps(name))
    )


def _read_all_details(assets: Path) -> tuple[dict[str, dict], dict[str, int]]:
    details = {}
    sizes = {}
    for shard in EVENT_DETAIL_SHARD_NAMES:
        path = assets / ("data-%s.js" % shard)
        if not path.exists():
            raise RuntimeError("缺少事件详情 shard：%s" % path.name)
        text = path.read_text(encoding="utf-8")
        marker = "window.__MING_EVENT_DETAILS__=Object.assign(window.__MING_EVENT_DETAILS__||{},"
        start = text.find(marker)
        if start < 0:
            raise RuntimeError("事件详情 shard 格式异常：%s" % path.name)
        start += len(marker)
        end = text.find(");", start)
        if end < 0:
            raise RuntimeError("事件详情 shard JSON 结束位置异常：%s" % path.name)
        rows = json.loads(text[start:end])
        for event_id, patch in rows.items():
            if event_id in details:
                raise RuntimeError("事件详情重复出现在多个 shard：%s" % event_id)
            if event_detail_shard_name(event_id) != shard:
                raise RuntimeError("事件详情 shard 路由错误：%s -> %s" % (event_id, shard))
            details[event_id] = patch
        sizes[shard] = path.stat().st_size
    return details, sizes


def check_site(root: Path) -> dict:
    assets = root / "assets"
    event_path = assets / "data-events.js"
    if not event_path.exists():
        raise RuntimeError("缺少 %s" % event_path)
    payload = read_chunk_payload(event_path)
    events = payload.get("events")
    if not isinstance(events, list):
        raise RuntimeError("data-events.js 缺少 events 数组")
    if any("sources" in event or "year_start" in event or "year_source" in event for event in events):
        raise RuntimeError("data-events.js 仍包含应延迟到详情 shard 的字段")
    if any("sourceCount" not in event for event in events):
        raise RuntimeError("data-events.js 摘要缺少 sourceCount")
    details, sizes = _read_all_details(assets)
    ids = [str(event.get("id") or "") for event in events]
    if len(ids) != len(set(ids)):
        raise RuntimeError("事件摘要 id 重复")
    if set(ids) != set(details):
        missing = sorted(set(ids) - set(details))[:8]
        extra = sorted(set(details) - set(ids))[:8]
        raise RuntimeError("事件详情覆盖异常：missing=%s extra=%s" % (missing, extra))
    return {
        "events_bytes": event_path.stat().st_size,
        "event_count": len(events),
        "detail_total_bytes": sum(sizes.values()),
        "detail_max_bytes": max(sizes.values()) if sizes else 0,
        "detail_max_name": max(sizes, key=sizes.get) if sizes else "",
        "detail_sizes": sizes,
    }


def split_site(root: Path) -> dict:
    assets = root / "assets"
    event_path = assets / "data-events.js"
    if not event_path.exists():
        raise RuntimeError("缺少 %s" % event_path)
    payload = read_chunk_payload(event_path)
    events = payload.get("events")
    if not isinstance(events, list):
        raise RuntimeError("data-events.js 缺少 events 数组")
    if events and "sourceCount" in events[0] and "sources" not in events[0]:
        return check_site(root)

    original = copy.deepcopy(events)
    summaries, details = split_event_transport(events)
    reconstructed = reconstruct_events(summaries, details)
    if reconstructed != original:
        raise RuntimeError("V12 events 摘要 + 详情补丁不可逆")

    rewritten = dict(payload)
    rewritten["events"] = summaries
    event_text = event_path.read_text(encoding="utf-8")
    event_path.write_text(_replace_payload(event_text, rewritten), encoding="utf-8")
    shards = split_detail_shards(details)
    for name, data in shards.items():
        (assets / ("data-%s.js" % name)).write_text(_detail_script(name, data), encoding="utf-8")

    stats = check_site(root)
    all_details, _ = _read_all_details(assets)
    if reconstruct_events(read_chunk_payload(event_path)["events"], all_details) != original:
        raise RuntimeError("V12 物理 shard 合并后无法恢复原始 events")
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="V12：拆分 web 事件摘要与确定性详情 shards")
    parser.add_argument("root", type=Path, nargs="?", default=Path("dist/full"))
    parser.add_argument("--check", action="store_true", help="只检查已拆分产物")
    args = parser.parse_args(argv)
    try:
        stats = check_site(args.root) if args.check else split_site(args.root)
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print("[FAIL] %s" % exc)
        return 1
    print(
        "V12 事件分层通过：core %.1f KiB · %d events · detail %d shards total %.1f KiB · max %s %.1f KiB"
        % (
            stats["events_bytes"] / 1024,
            stats["event_count"],
            EVENT_DETAIL_SHARD_COUNT,
            stats["detail_total_bytes"] / 1024,
            stats["detail_max_name"],
            stats["detail_max_bytes"] / 1024,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
