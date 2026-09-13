# -*- coding: utf-8 -*-
"""让 README 的公开规模口径与最终模型保持一致。

README 是项目首页，但其中地点/事件等数字过去靠人工维护，数据勘误后容易滞后。
本脚本直接复用 ``generate_report.build_scope("full")`` 的最终模型口径，只更新
README 中少数明确标记的公开统计与 V2 导航摘要，不碰长篇说明正文。

用法：
    python src/sync_readme.py          # 原地更新 README.md
    python src/sync_readme.py --check  # 只检查；不一致时退出码 1
"""
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
    chapters = int(m["chapters"])
    locations = int(m["locations"])
    located = int(m["locatedLocations"])
    events = int(m["events"])
    timed = int(m["timedEvents"])
    unknown = int(m["unknownEvents"])
    characters = int(m["characters"])
    relations = int(m["relations"])
    unlocated = locations - located
    located_pct = 100.0 * located / max(locations, 1)
    quotes = _quote_count()

    text = source
    rows = {
        "来源章节": "| 来源章节 | %d | 七部全部章节，抽取覆盖 100%% |" % chapters,
        "地点": "| 地点 | %d（已定位 %d，%.1f%%） | 未定位的 %d 个如实标为「待核验」，不硬填坐标 |"
        % (locations, located, located_pct, unlocated),
        "人物": "| 人物 | %d | 含出场章节、别名、势力、身份 |" % characters,
        "事件": "| 事件 | %d（有年份 %d） | 未知年份 %d 件单独保留，不混入历史顺序 |"
        % (events, timed, unknown),
        "关系": "| 关系 | %d | 含亲属、政治、军事、派系等类别 |" % relations,
    }
    for label, line in rows.items():
        text = _replace_one(text, r"^\| %s \|.*$" % re.escape(label), line, "规模表/%s" % label)

    nav = (
        "**全局叙事**：`总览` `分布` `时间轴` `帝王` `年谱`　·　"
        "**实体索引**：`人物` `地点` `事件` `关系`　·　"
        "**探索分析**：`图谱` `地图` `洞察`"
    )
    text = _replace_one(
        text,
        r"^(?:`总览` .*`洞察`|\*\*全局叙事\*\*：.*)$",
        nav,
        "V2 导航摘要",
    )

    if "<!-- README_V2_JOURNEYS -->" not in text:
        text = text.replace(
            nav + "\n",
            nav
            + "\n\n<!-- README_V2_JOURNEYS -->\n"
            + "> V2 首页另提供三条问题导向的探索路径：**人物脉络**、**时间脉络**、**空间与结构**；"
            + "顶部导航与深链仍使用原有 12 个 view id。\n",
            1,
        )

    text = _replace_one(
        text,
        r"^- \*\*地点\*\*：\d+ 张地点卡",
        "- **地点**：%d 张地点卡" % locations,
        "地点视图数量",
    )
    text = _replace_one(
        text,
        r"（\d+ 位(?:核心)?人物的语录均经原文核实，见 `data/character_quotes\.json`）",
        "（%d 位人物的语录均经原文核实，见 `data/character_quotes.json`）" % quotes,
        "人物语录覆盖",
    )

    # web target 已包含页面实际注册的 Service Worker，README 同步反映完整产物。
    text = text.replace(
        "拆成 `assets/app.css`、`assets/app.js`、`assets/data.js`，便于本地逐文件调试",
        "拆成 `assets/app.css`、`assets/app.js`、`assets/data.js` 并复制 `sw.js`，便于本地逐文件调试",
    )

    marker = "<!-- README_STATS_SYNC -->"
    if marker not in text:
        anchor = "| 年谱 | 165 人 | 主要人物生卒横向展开，与年号对位 |\n"
        if anchor not in text:
            raise SystemExit("README 同步锚点异常（规模表尾部）")
        text = text.replace(
            anchor,
            anchor
            + "\n"
            + marker
            + "\n> 上表的章节 / 地点 / 人物 / 事件 / 关系统计由 `src/sync_readme.py` 从最终模型自动刷新；"
            + "发布同步工作流会与根目录 `index.html` 一起维护。\n",
            1,
        )

    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 README 中的最终模型统计")
    parser.add_argument("--check", action="store_true", help="只检查 README 是否已同步")
    args = parser.parse_args(argv)

    source = README.read_text(encoding="utf-8")
    updated = render_readme(source)
    if updated == source:
        print("README 已与最终模型一致")
        return 0
    if args.check:
        print("README 与最终模型不一致；请运行 python src/sync_readme.py", file=sys.stderr)
        return 1
    README.write_text(updated, encoding="utf-8")
    print("README 已同步：%d → %d 字符" % (len(source), len(updated)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
