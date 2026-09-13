# -*- coding: utf-8 -*-
"""校验 web/ 拆分产物能否逐字节还原 generate_report.HTML_TEMPLATE。"""
import io
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
import generate_report as G  # noqa: E402

skel = io.open(BASE / "web/template/index.html", encoding="utf-8").read()
css = io.open(BASE / "web/css/app.css", encoding="utf-8").read()
js = io.open(BASE / "web/js/app.js", encoding="utf-8").read()
doc = skel.replace("/*{{INLINE_CSS}}*/", css).replace("/*{{INLINE_JS}}*/", js)
old = G.HTML_TEMPLATE

out = []
out.append("old=%d new=%d equal=%s" % (len(old), len(doc), old == doc))
if old != doc:
    n = min(len(old), len(doc))
    i = 0
    while i < n and old[i] == doc[i]:
        i += 1
    out.append("first_diff=%d" % i)
    out.append("OLD %r" % old[max(0, i - 60):i + 80])
    out.append("NEW %r" % doc[max(0, i - 60):i + 80])
    out.append("OLD_tail %r" % old[-80:])
    out.append("NEW_tail %r" % doc[-80:])
io.open(BASE / ".dump/_check_split_out.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))
