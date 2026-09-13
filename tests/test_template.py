# -*- coding: utf-8 -*-
"""模板层测试：骨架锚点、拆分等价性、两条构建路径一致性。

这些用例只依赖 web/ 与 src/，不需要 data/，可离线在 CI 跑。
"""

from __future__ import annotations

import _support

import build as B


def test_skeleton_has_anchors():
    """骨架必须保留两个内联锚点，否则 standalone 构建会静默丢样式/脚本。"""
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "/*{{INLINE_CSS}}*/" in skeleton
    assert "/*{{INLINE_JS}}*/" in skeleton
    assert skeleton.count("__TITLE__") == 2, "标题占位符应恰好出现在 <title> 与 <h1> 两处"
    assert skeleton.rstrip().endswith("</html>")


def test_split_is_lossless():
    """web/ 三件套拼回来必须与 generate_report.HTML_TEMPLATE 逐字节相同。

    这是 Phase 4 拆分的验收底线：拆分本身不得引入任何字符变化。
    """
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    css = B.G.CSS_PATH.read_text(encoding="utf-8")
    js = B.G.JS_PATH.read_text(encoding="utf-8")
    rebuilt = skeleton.replace("/*{{INLINE_CSS}}*/", css).replace("/*{{INLINE_JS}}*/", js)
    assert rebuilt == B.G.HTML_TEMPLATE
    assert len(rebuilt) == len(B.G.HTML_TEMPLATE)


def test_js_holds_data_placeholders():
    """DATA / INSIGHT_DATA 占位符随脚本一起被拆到 app.js，必须仍在。"""
    js = B.G.JS_PATH.read_text(encoding="utf-8")
    assert js.count("const DATA=__DATA__;") == 1
    assert js.count("const INSIGHT_DATA=__INSIGHT_DATA__;") == 1
    assert js.startswith("const DATA=__DATA__;")


def test_css_has_no_template_tokens():
    """样式文件里不该出现任何模板占位符。"""
    css = B.G.CSS_PATH.read_text(encoding="utf-8")
    for token in ("__DATA__", "__TITLE__", "__INSIGHT_DATA__", "{{INLINE"):
        assert token not in css, token


def test_compose_document_is_used_by_build():
    """build.py 的 standalone 路径必须复用 generate_report 的注入实现。"""
    import inspect

    src = inspect.getsource(B.render_standalone)
    assert "compose_document" in src


def test_compose_document_injects_all_tokens():
    """注入后不得残留任何占位符，且数据确实进去了。"""
    payload = _support.payload("full")
    doc = B.G.compose_document(payload)
    for token in ("__DATA__", "__INSIGHT_DATA__", "__TITLE__"):
        assert token not in doc, token
    assert doc.count('"metrics"') >= 1
    assert '"schemaVersion"' in doc
    assert doc.rstrip().endswith("</html>")


def test_build_py_and_generate_report_agree():
    """两条构建路径必须产出同一份字符流（防止将来改一处漏一处）。"""
    payload = _support.payload("full")
    assert B.render_standalone(payload) == B.G.compose_document(payload)


def test_app_js_has_phase6_hooks():
    """Phase 6 的入口必须留在脚本里（deep link / 高亮 / tab 语义）。"""
    js = B.G.JS_PATH.read_text(encoding="utf-8")
    for token in ("function applyDeepLink", "function readHash", "function writeHash",
                  "function locatePersonCard", "function markTerms", "aria-selected",
                  "data-char=", "function showPerson"):
        assert token in js, token
    assert js.count("const DATA=__DATA__;") == 1, "重构时不得把数据占位符弄丢"


def test_css_phase6_rules_and_balance():
    """样式表必须括号平衡，且带上高亮/闪烁两条新规则。"""
    css = B.G.CSS_PATH.read_text(encoding="utf-8")
    assert css.count("{") == css.count("}"), "CSS 花括号不平衡（单行模板最易犯）"
    assert "mark.hl" in css
    assert "character-card.flash" in css
