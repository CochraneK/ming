# -*- coding: utf-8 -*-
"""把 V3 产品体验层的 CSS / JS 镜像进 standalone 模板。

``web/css/experience.css`` 与 ``web/js/experience.js`` 是全局搜索、首页数据叙事、
图谱阅读器的人工维护源。standalone 仍需保持单文件离线可用，因此发布前把两者
以内联生成镜像写入 ``web/template/index.html``；模板中的对应块不应直接编辑。

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
CSS_SOURCE = BASE / "web" / "css" / "experience.css"
JS_SOURCE = BASE / "web" / "js" / "experience.js"

STYLE_ATTR = 'data-generated-from="web/css/experience.css"'
SCRIPT_ATTR = 'data-generated-from="web/js/experience.js"'
STYLE_START = "/* EXPERIENCE_CSS_SYNC_START */"
STYLE_END = "/* EXPERIENCE_CSS_SYNC_END */"
SCRIPT_START = "/* EXPERIENCE_SYNC_START */"
SCRIPT_END = "/* EXPERIENCE_SYNC_END */"


def generated_block(css: str, js: str) -> str:
    return (
        '<style %s>\n%s\n%s\n%s\n</style>\n'
        '<script %s>\n%s\n%s\n%s\n</script>'
        % (
            STYLE_ATTR, STYLE_START, css.rstrip(), STYLE_END,
            SCRIPT_ATTR, SCRIPT_START, js.rstrip(), SCRIPT_END,
        )
    )


def render_template(source: str, css: str, js: str) -> str:
    block = generated_block(css, js)
    pattern = re.compile(
        r'<style\s+data-generated-from="web/css/experience\.css">\n'
        r'/\* EXPERIENCE_CSS_SYNC_START \*/.*?/\* EXPERIENCE_CSS_SYNC_END \*/\n</style>\n'
        r'<script\s+data-generated-from="web/js/experience\.js">\n'
        r'/\* EXPERIENCE_SYNC_START \*/.*?/\* EXPERIENCE_SYNC_END \*/\n</script>',
        re.DOTALL,
    )
    if pattern.search(source):
        updated, count = pattern.subn(lambda _m: block, source, count=1)
    else:
        # 兼容这个分支最早只同步 JS 的过渡形态：若存在旧 script 镜像，整体升级成 CSS+JS。
        old_script = re.compile(
            r'<script\s+data-generated-from="web/js/experience\.js">\n'
            r'/\* EXPERIENCE_SYNC_START \*/.*?/\* EXPERIENCE_SYNC_END \*/\n</script>',
            re.DOTALL,
        )
        if old_script.search(source):
            updated, count = old_script.subn(lambda _m: block, source, count=1)
        else:
            if source.count("</body>") != 1:
                raise SystemExit("体验层插入锚点异常：</body> 数量不是 1")
            updated = source.replace("</body>", block + "\n</body>", 1)
            count = 1
    if count != 1:
        raise SystemExit("体验层镜像锚点异常：匹配 %d 处" % count)
    expected = (STYLE_ATTR, SCRIPT_ATTR, STYLE_START, STYLE_END, SCRIPT_START, SCRIPT_END)
    if any(updated.count(token) != 1 for token in expected):
        raise SystemExit("体验层镜像标记数量异常")
    return updated


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 V3 experience CSS/JS 到 standalone 模板")
    parser.add_argument("--check", action="store_true", help="只检查体验层镜像是否最新")
    args = parser.parse_args(argv)

    source = TEMPLATE.read_text(encoding="utf-8")
    css = CSS_SOURCE.read_text(encoding="utf-8")
    js = JS_SOURCE.read_text(encoding="utf-8")
    updated = render_template(source, css, js)
    if updated == source:
        print("体验层镜像已与 experience.css / experience.js 一致")
        return 0
    if args.check:
        print("体验层镜像已过期；请运行 python src/sync_experience.py")
        return 1
    TEMPLATE.write_text(updated, encoding="utf-8")
    print("体验层镜像已同步：CSS %d 字符 · JS %d 字符" % (len(css), len(js)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
