# -*- coding: utf-8 -*-
"""Phase 4 迁移：把 generate_report.py 内的 HTML_TEMPLATE 字面量换成 web/ 读取器。

幂等：若已迁移过则直接退出。
"""
import io
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
P = BASE / "src" / "generate_report.py"
src = io.open(P, encoding="utf-8").read()

if "def load_template()" in src:
    print("already migrated")
    raise SystemExit(0)

marker = "HTML_TEMPLATE = r'''"
i = src.index(marker)
# 模板结束标记：全文仅两处 '''，第二处即模板结尾（其后为 \n\n\ndef render）
j = src.index("'''", i + len(marker))
end = j + len("'''")

new_block = '''WEB_DIR = BASE / "web"
TEMPLATE_PATH = WEB_DIR / "template" / "index.html"
CSS_PATH = WEB_DIR / "css" / "app.css"
JS_PATH = WEB_DIR / "js" / "app.js"


def load_template() -> str:
    """读取 web/ 下的骨架 + 样式 + 脚本，内联回单文件文档。

    Phase 4 之前整份模板是 Python 里的 12.5 万字符字面量，改动要同时动
    HTML/CSS/JS 三种语言，编辑体验差且无法语法检查。现在拆到 web/：
    - web/template/index.html  骨架，含 /*{{INLINE_CSS}}*/ 与 /*{{INLINE_JS}}*/ 两个锚点
    - web/css/app.css          样式
    - web/js/app.js            脚本（首行 const DATA=__DATA__; 由 render() 注入）

    拼接结果与拆分前逐字节等价，可用 .dump/_check_split.py 复核。
    """
    skeleton = TEMPLATE_PATH.read_text(encoding="utf-8")
    css = CSS_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    return skeleton.replace("/*{{INLINE_CSS}}*/", css).replace("/*{{INLINE_JS}}*/", js)


HTML_TEMPLATE = load_template()'''

out = src[:i] + new_block + src[end:]
io.open(P, "w", encoding="utf-8", newline="").write(out)
print("migrated: removed %d chars, inserted %d chars" % (end - i, len(new_block)))
