# -*- coding: utf-8 -*-
"""Phase 4 一次性拆分脚本：把 generate_report.py 里的单体 HTML 模板拆成

    web/template/index.html   （骨架，含 {{INLINE_CSS}}/{{INLINE_JS}}/{{TITLE}}/{{DATA}}/{{INSIGHT_DATA}} 占位）
    web/css/app.css           （原 <style> 内容）
    web/js/app.js             （原 <script> 内容）

拆分后 Python 侧不再维护大段 HTML/CSS/JS；构建时由 src/build.py 重新内联成单文件。
本脚本只读 generate_report.py（不改），产物为三个新文件。
"""
import io, os, re

BASE = r"D:\2026\WB项目\明朝"
SRC = os.path.join(BASE, "src", "generate_report.py")

text = io.open(SRC, encoding="utf-8").read()

start = text.find("HTML_TEMPLATE = r'''")
assert start != -1, "找不到 HTML_TEMPLATE 起点"
body_start = start + len("HTML_TEMPLATE = r'''")
end = text.find("'''", body_start)
assert end != -1, "找不到 HTML_TEMPLATE 终点"
template = text[body_start:end]
print("模板长度", len(template))

# 抽取 CSS
m_css = re.search(r"<style>(.*?)</style>", template, re.S)
assert m_css, "找不到 <style>"
css = m_css.group(1)
# 抽取 JS（取最后一个 script 块，模板里只有一个）
scripts = list(re.finditer(r"<script>(.*?)</script>", template, re.S))
assert len(scripts) == 1, "script 块数量异常: %d" % len(scripts)
js = scripts[0].group(1)
print("CSS %d 字符 / JS %d 字符" % (len(css), len(js)))

os.makedirs(os.path.join(BASE, "web", "css"), exist_ok=True)
os.makedirs(os.path.join(BASE, "web", "js"), exist_ok=True)
os.makedirs(os.path.join(BASE, "web", "template"), exist_ok=True)

io.open(os.path.join(BASE, "web", "css", "app.css"), "w", encoding="utf-8", newline="\n").write(css.strip("\n") + "\n")
io.open(os.path.join(BASE, "web", "js", "app.js"), "w", encoding="utf-8", newline="\n").write(js.strip("\n") + "\n")

# 骨架：把 style / script 内容换成占位符
shell = template
shell = shell[:m_css.start(1)] + "\n/*{{INLINE_CSS}}*/\n" + shell[m_css.end(1):]
# script 位置在替换 CSS 后偏移不变（CSS 在 script 之前，长度变了）→ 重新定位
s2 = re.search(r"(<script>)(.*?)(</script>)", shell, re.S)
shell = shell[:s2.start(2)] + "\n/*{{INLINE_JS}}*/\n" + shell[s2.end(2):]

io.open(os.path.join(BASE, "web", "template", "index.html"), "w", encoding="utf-8", newline="\n").write(shell)

print("占位符检查:",
      "{{INLINE_CSS}}" in shell, "{{INLINE_JS}}" in shell,
      "__DATA__" in shell, "__TITLE__" in shell, "__INSIGHT_DATA__" in shell)
print("骨架 %d 字符" % len(shell))
