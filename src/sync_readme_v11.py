# -*- coding: utf-8 -*-
"""在基础 README 自动同步后补充 V11 时间域物理分层说明。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
README = BASE / "README.md"

INTRO = "基于《明朝那些事儿》七部 156 章全文抽取整理的静态知识库。在线版采用 V11 分层按需交付：首页只加载 `boot-data.js`，全局搜索加载轻量 `search-index.js`；人物为 `data-characters.js` + 16 个人物详情 shard，地点为 `data-locations.js` + 8 个地点详情 shard + 独立章节/航线块；时间域进一步把年谱专用 `lifespans` 从 `data-time.js` 拆成 `data-lifespans.js`，因此年谱只加载人物卡片 + 生卒数据，时间轴/帝王才加载 timeline。`standalone.html` 仍是完整单文件离线版。"
PAGES = "GitHub Pages：`https://cochranek.github.io/ming/`（根 `index.html` 为 V11 分层按需版；`standalone.html` 为可下载 / 双击打开的完整离线版）"
STATS = "> 上表的章节 / 地点 / 人物 / 事件 / 关系统计由 `src/sync_readme.py` 从最终模型自动刷新；发布同步工作流会同时维护在线 V11 `index.html + assets/` 与离线 `standalone.html`。"
TARGET = "| `--target standalone\\|web` | 默认 `standalone`＝CSS/JS/DATA 全内联到 `standalone.html`；`web`＝输出到 `dist/<scope>/`。人物：`data-characters.js` + 16 个 `data-character-detail-*`；地点：`data-locations.js` + 8 个 `data-location-detail-*`，另有 `data-place-chapters.js` / `data-voyages.js`；生产发布随后由 `src/split_time_asset_v11.py` 把 `data-time.js` 中的年谱 `lifespans` 无损拆成 `data-lifespans.js`，其余事件 / 关系 / 图谱 / 洞察 / 元数据继续独立按需加载 |"
DELIVERY = "`standalone` 构建继续内联完整最终 DATA；在线生产链路对同一 payload 做可逆传输分区，再由 `src/split_time_asset_v11.py` 仅在物理交付层把 `lifespans` 从 `data-time.js` 拆为 `data-lifespans.js`。人物与地点仍采用‘轻量摘要 + 详情补丁 + 确定性 shard’；加载全部物理块后可逐值恢复原始最终模型。不维护 `data-full.js`、`data-character-details.js`、`data-location-details.js` 或旧 `data-space.js` 单体包。"


def _replace_prefix(lines: list[str], prefix: str, replacement: str, label: str) -> None:
    matches = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError("README V11 锚点异常（%s）：%d" % (label, len(matches)))
    lines[matches[0]] = replacement


def render_readme(source: str) -> str:
    lines = source.splitlines()
    _replace_prefix(lines, "基于《明朝那些事儿》七部 156 章全文抽取整理的静态知识库。", INTRO, "intro")
    _replace_prefix(lines, "GitHub Pages：", PAGES, "pages")
    _replace_prefix(lines, "> 上表的章节 / 地点 / 人物 / 事件 / 关系统计由", STATS, "stats")
    _replace_prefix(lines, "| `--target standalone\\|web` |", TARGET, "target")
    _replace_prefix(lines, "`standalone` 构建继续", DELIVERY, "delivery")
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 README 的 V11 时间域交付说明")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    source = README.read_text(encoding="utf-8")
    try:
        updated = render_readme(source)
    except RuntimeError as exc:
        print("[FAIL] %s" % exc, file=sys.stderr)
        return 2
    if updated == source:
        print("README V11 时间域说明已同步")
        return 0
    if args.check:
        print("README 尚未同步 V11 时间域说明", file=sys.stderr)
        return 1
    README.write_text(updated, encoding="utf-8")
    print("README V11 时间域说明已写入")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
