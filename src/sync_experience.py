# -*- coding: utf-8 -*-
"""把 web/js/experience.js 镜像进 standalone 模板。

``experience.js`` 是 V3 产品体验增强层（全局搜索 / 首页数据叙事 / 图谱阅读器）的
唯一人工维护源。standalone 仍需保持单文件离线可用，因此发布前把它以内联脚本镜像
到 web/template/index.html；模板中的镜像不应直接编辑。

用法：
    python src/sync_experience.py
    python src/sync_experience.py --check
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TEMPLATE = BASE / "web" / "template" / "index.html"
SOURCE = BASE / "web" / "js" / "experience.js"

SOURCE_ATTR = 'data-generated-from="web/js/experience.js"'
START = "/* EXPERIENCE_SYNC_START */"
END = "/* EXPERIENCE_SYNC_END */"


def generated_block(js: str) -> str:
    return '<script %s>\n%s\n%s\n%s\n</script>' % (
        SOURCE_ATTR, START, js.rstrip(), END
    )


def render_template(source: str, js: str) -> str:
    block = generated_block(js)
    pattern = re.compile(
        r'<script\s+data-generated-from="web/js/experience\.js">\n'
        r'/\* EXPERIENCE_SYNC_START \*/.*?/\* EXPERIENCE_SYNC_END \*/\n</script>',
        re.DOTALL,
    )
    if pattern.search(source):
        updated, count = pattern.subn(lambda _m: block, source, count=1)
    else:
        if source.count("</body>") != 1:
            raise SystemExit("体验层插入锚点异常：</body> 数量不是 1")
        updated = source.replace("</body>", block + "\n</body>", 1)
        count = 1
    if count != 1:
        raise SystemExit("体验层镜像锚点异常：匹配 %d 处" % count)
    if updated.count(SOURCE_ATTR) != 1 or updated.count(START) != 1 or updated.count(END) != 1:
        raise SystemExit("体验层镜像标记数量异常")
    return updated


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 experience.js 到 standalone 模板")
    parser.add_argument("--check", action="store_true", help="只检查体验层镜像是否最新")
    args = parser.parse_args(argv)

    source = TEMPLATE.read_text(encoding="utf-8")
    js = SOURCE.read_text(encoding="utf-8")
    updated = render_template(source, js)
    if updated == source:
        print("体验层镜像已与 experience.js 一致")
        return 0
    if args.check:
        print("体验层镜像已过期；请运行 python src/sync_experience.py")
        return 1
    TEMPLATE.write_text(updated, encoding="utf-8")
    print("体验层镜像已同步：%d 字符" % len(js))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
