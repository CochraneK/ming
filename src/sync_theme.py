# -*- coding: utf-8 -*-
"""把 web/css/theme.css 镜像进 standalone 模板的主题样式块。

``theme.css`` 是视觉主题 / V2 信息架构样式的唯一人工维护源。模板仍需包含
主题 CSS，才能维持「下载一个 index.html 即可离线打开」的 standalone 交付形态；
因此模板里的对应 ``<style>`` 块是生成镜像，不应直接编辑。

用法：
    python src/sync_theme.py          # 更新 web/template/index.html
    python src/sync_theme.py --check  # 只检查，不写文件
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TEMPLATE = BASE / "web" / "template" / "index.html"
THEME = BASE / "web" / "css" / "theme.css"

SOURCE_ATTR = 'data-generated-from="web/css/theme.css"'
START = "/* THEME_SYNC_START */"
END = "/* THEME_SYNC_END */"
LEGACY_START = "/* ===== Visual polish 2026-09 · Ming digital-humanities skin ===== */"


def generated_block(theme: str) -> str:
    return (
        '<style %s>\n%s\n%s\n%s\n</style>'
        % (SOURCE_ATTR, START, theme.rstrip(), END)
    )


def render_template(source: str, theme: str) -> str:
    block = generated_block(theme)
    generated_pattern = re.compile(
        r'<style\s+data-generated-from="web/css/theme\.css">\n'
        r'/\* THEME_SYNC_START \*/.*?/\* THEME_SYNC_END \*/\n</style>',
        re.DOTALL,
    )
    if generated_pattern.search(source):
        updated, count = generated_pattern.subn(lambda _m: block, source, count=1)
    else:
        # 首次迁移：只接受紧跟视觉主题标记的独立 style 块，避免误伤 INLINE_CSS。
        legacy_pattern = re.compile(
            r"<style>\n(?=" + re.escape(LEGACY_START) + r").*?</style>",
            re.DOTALL,
        )
        updated, count = legacy_pattern.subn(lambda _m: block, source, count=1)
    if count != 1:
        raise SystemExit("主题镜像锚点异常：匹配 %d 处" % count)
    if updated.count(SOURCE_ATTR) != 1 or updated.count(START) != 1 or updated.count(END) != 1:
        raise SystemExit("主题镜像标记数量异常")
    return updated


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 theme.css 到 standalone 模板")
    parser.add_argument("--check", action="store_true", help="只检查主题镜像是否最新")
    args = parser.parse_args(argv)

    source = TEMPLATE.read_text(encoding="utf-8")
    theme = THEME.read_text(encoding="utf-8")
    updated = render_template(source, theme)
    if updated == source:
        print("主题镜像已与 theme.css 一致")
        return 0
    if args.check:
        print("主题镜像已过期；请运行 python src/sync_theme.py")
        return 1
    TEMPLATE.write_text(updated, encoding="utf-8")
    print("主题镜像已同步：%d 字符" % len(theme))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
