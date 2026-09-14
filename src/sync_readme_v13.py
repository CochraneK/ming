# -*- coding: utf-8 -*-
"""在基础/V11/V12 README 同步后补充 V13 关系 core + metadata 交付说明。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
README = BASE / "README.md"

INTRO = "基于《明朝那些事儿》七部 156 章全文抽取整理的静态知识库。在线版采用 V13 分层按需交付：首页只加载 `boot-data.js`，全局搜索加载轻量 `search-index.js`；人物为 `data-characters.js` + 16 个人物详情 shard，地点为 `data-locations.js` + 8 个地点详情 shard + 独立章节/航线块，年谱使用独立 `data-lifespans.js`；事件为轻量 `data-events.js` + 8 个事件详情 shard；关系索引进一步只加载可见字段组成的 `data-relations.js` core，完整关系 id / 端点类型 / 来源键等 metadata 只在 full DATA 时由 `data-relation-meta.js` 补回。`standalone.html` 仍是完整单文件离线版。"
PAGES = "GitHub Pages：`https://cochranek.github.io/ming/`（根 `index.html` 为 V13 分层按需版；`standalone.html` 为可下载 / 双击打开的完整离线版）"
STATS = "> 上表的章节 / 地点 / 人物 / 事件 / 关系统计由 `src/sync_readme.py` 从最终模型自动刷新；发布同步工作流会同时维护在线 V13 `index.html + assets/` 与离线 `standalone.html`。"
TARGET = "| `--target standalone\\|web` | 默认 `standalone`＝CSS/JS/DATA 全内联到 `standalone.html`；`web`＝输出到 `dist/<scope>/`。生产发布在基础 web 构建后依次执行 V11 时间分层、V12 事件分层与 V13 关系分层：人物/地点/事件详情使用确定性 shard，时间另有 `data-lifespans.js`；关系为轻量 `data-relations.js` core + 仅 full DATA 才加载的 `data-relation-meta.js`；图谱 / 洞察 / 元数据继续独立按需加载 |"
DELIVERY = "`standalone` 构建继续内联完整最终 DATA；在线生产链路对同一 payload 做可逆传输分区：`src/split_time_asset_v11.py` 拆出 `lifespans`，`src/split_event_asset_v12.py` 把 events 变换成摘要核心 + 8 个详情 shard，`src/split_relation_asset_v13.py` 再把 relations 变换成可见 core + deferred metadata。加载全部物理块后可逐值恢复原始最终模型；不维护 `data-full.js`、`data-character-details.js`、`data-location-details.js`、`data-event-details.js` 或旧 `data-space.js` 单体包。"


def _replace_prefix(lines: list[str], prefix: str, replacement: str, label: str) -> None:
    matches = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError("README V13 锚点异常（%s）：%d" % (label, len(matches)))
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
    parser = argparse.ArgumentParser(description="同步 README 的 V13 关系分层说明")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    source = README.read_text(encoding="utf-8")
    try:
        updated = render_readme(source)
    except RuntimeError as exc:
        print("[FAIL] %s" % exc, file=sys.stderr)
        return 2
    if updated == source:
        print("README V13 关系分层说明已同步")
        return 0
    if args.check:
        print("README 尚未同步 V13 关系分层说明", file=sys.stderr)
        return 1
    README.write_text(updated, encoding="utf-8")
    print("README V13 关系分层说明已写入")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
