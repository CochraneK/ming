# -*- coding: utf-8 -*-
"""让 README 的公开规模口径与最终模型 / 当前交付架构保持一致。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_report as G  # noqa: E402

README = BASE / "README.md"
QUOTES = BASE / "data" / "character_quotes.json"


def _replace_one(text: str, pattern: str, replacement: str, label: str) -> str:
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit("README 同步锚点异常（%s）：匹配 %d 处" % (label, count))
    return new


def _quote_count() -> int:
    with QUOTES.open(encoding="utf-8") as f:
        data = json.load(f)
    return sum(1 for key, value in data.items() if not str(key).startswith("_") and str(value).strip())


def render_readme(source: str) -> str:
    model = G.build_scope("full")
    m = model["metrics"]
    chapters = int(m["chapters"]);locations = int(m["locations"]);located = int(m["locatedLocations"])
    events = int(m["events"]);timed = int(m["timedEvents"]);unknown = int(m["unknownEvents"])
    characters = int(m["characters"]);relations = int(m["relations"])
    unlocated = locations - located;located_pct = 100.0 * located / max(locations, 1);quotes = _quote_count()

    text = source
    rows = {
        "来源章节": "| 来源章节 | %d | 七部全部章节，抽取覆盖 100%% |" % chapters,
        "地点": "| 地点 | %d（已定位 %d，%.1f%%） | 未定位的 %d 个如实标为「待核验」，不硬填坐标 |" % (locations, located, located_pct, unlocated),
        "人物": "| 人物 | %d | 含出场章节、别名、势力、身份 |" % characters,
        "事件": "| 事件 | %d（有年份 %d） | 未知年份 %d 件单独保留，不混入历史顺序 |" % (events, timed, unknown),
        "关系": "| 关系 | %d | 含亲属、政治、军事、派系等类别 |" % relations,
    }
    for label, line in rows.items():
        text = _replace_one(text, r"^\| %s \|.*$" % re.escape(label), line, "规模表/%s" % label)

    nav = (
        "**全局叙事**：`总览` `分布` `时间轴` `帝王` `年谱`　·　"
        "**实体索引**：`人物` `地点` `事件` `关系`　·　"
        "**探索分析**：`图谱` `地图` `洞察`"
    )
    text = _replace_one(text, r"^(?:`总览` .*`洞察`|\*\*全局叙事\*\*：.*)$", nav, "V2 导航摘要")
    if "<!-- README_V2_JOURNEYS -->" not in text:
        text = text.replace(nav + "\n", nav + "\n\n<!-- README_V2_JOURNEYS -->\n> V2 首页另提供三条问题导向的探索路径：**人物脉络**、**时间脉络**、**空间与结构**；顶部导航与深链仍使用原有 12 个 view id。\n", 1)

    text = _replace_one(text, r"^- \*\*地点\*\*：\d+ 张地点卡", "- **地点**：%d 张地点卡" % locations, "地点视图数量")
    text = _replace_one(text, r"（\d+ 位(?:核心)?人物的语录均经原文核实，见 `data/character_quotes\.json`）", "（%d 位人物的语录均经原文核实，见 `data/character_quotes.json`）" % quotes, "人物语录覆盖")

    text = re.sub(
        r"^基于《明朝那些事儿》七部 156 章全文抽取整理的.*$",
        "基于《明朝那些事儿》七部 156 章全文抽取整理的静态知识库。在线版采用 V10 实体与空间分层按需交付：首页只加载 `boot-data.js`，全局搜索加载轻量 `search-index.js`；人物保留 `data-characters.js` + 16 个人物详情 shard；地点域进一步拆成轻量 `data-locations.js`、8 个 `data-location-detail-00.js` … `07.js`、独立 `data-place-chapters.js` 与 `data-voyages.js`。地点索引和默认地图只取地点摘要，打开单个地点才取其详情 shard + 事件/洞察，切到“按章节”或郑和航线时才补对应数据。同时保留 `standalone.html` 单文件离线版。",
        text, count=1, flags=re.MULTILINE,
    )
    text = _replace_one(text, r"^GitHub Pages：.*$", "GitHub Pages：`https://cochranek.github.io/ming/`（根 `index.html` 为 V10 实体与空间分层按需版；`standalone.html` 为可下载 / 双击打开的完整离线版）", "V10 在线入口")
    text = text.replace("python src/build.py                 # 构建全书单文件 index.html", "python src/build.py                 # 构建全书单文件 standalone.html")
    text = re.sub(
        r"^\| `--target standalone\\\|web` \|.*$",
        "| `--target standalone\\|web` | 默认 `standalone`＝CSS/JS/DATA 全内联到 `standalone.html`；`web`＝输出到 `dist/<scope>/`。人物：`data-characters.js` + 16 个 `data-character-detail-*`；地点：`data-locations.js` + 8 个 `data-location-detail-*`，按章节为 `data-place-chapters.js`，航线为 `data-voyages.js`；事件 / 关系 / 时间 / 图谱 / 洞察 / 元数据继续独立按需加载 |",
        text, count=1, flags=re.MULTILINE,
    )
    text = re.sub(
        r"^`standalone` 构建.*$",
        "`standalone` 构建继续内联完整最终 DATA；`web` 构建对同一 payload 做可逆传输分区。人物与地点都采用‘轻量摘要 + 详情补丁 + 确定性 shard’，空间的章节索引和航线再独立拆块；加载全部物理块后可逐值恢复原始最终模型。不维护 `data-full.js`、`data-character-details.js`、`data-location-details.js` 或旧 `data-space.js` 单体包。",
        text, count=1, flags=re.MULTILINE,
    )

    marker = "<!-- README_STATS_SYNC -->"
    note = "> 上表的章节 / 地点 / 人物 / 事件 / 关系统计由 `src/sync_readme.py` 从最终模型自动刷新；发布同步工作流会同时维护在线 V10 `index.html + assets/` 与离线 `standalone.html`。"
    if marker not in text:
        anchor = "| 年谱 | 165 人 | 主要人物生卒横向展开，与年号对位 |\n"
        if anchor not in text: raise SystemExit("README 同步锚点异常（规模表尾部）")
        text = text.replace(anchor, anchor + "\n" + marker + "\n" + note + "\n", 1)
    else:
        text = _replace_one(text, r"^> 上表的章节 / 地点 / 人物 / 事件 / 关系统计由 `src/sync_readme\.py`.*$", note, "V10 发布说明")
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 README 中的最终模型统计与交付说明")
    parser.add_argument("--check", action="store_true", help="只检查 README 是否已同步")
    args = parser.parse_args(argv)
    source = README.read_text(encoding="utf-8");updated = render_readme(source)
    if updated == source:
        print("README 已与最终模型和 V10 交付架构一致");return 0
    if args.check:
        print("README 与最终模型或 V10 交付架构不一致；请运行 python src/sync_readme.py", file=sys.stderr);return 1
    README.write_text(updated, encoding="utf-8")
    print("README 已同步：%d → %d 字符" % (len(source), len(updated)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
