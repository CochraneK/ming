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


def test_data_placeholders_appear_exactly_once():
    """数据占位符在全模板里只能各出现一次。

    这条是体积事故的防腐层：占位符是纯字符串替换，若它另外出现在骨架的注释/文案里
    （例如守卫脚本注释里提到那个占位符名），整份 payload 会被注入两遍，
    单文件体积凭空翻倍（实测 5.6 MB → 11.4 MB）且极难察觉。
    """
    tmpl = B.G.HTML_TEMPLATE
    assert tmpl.count("__DATA__") == 1, "数据占位符只能出现一次"
    assert tmpl.count("__INSIGHT_DATA__") == 1
    assert tmpl.count("__TITLE__") == 2
    # 骨架本身不该出现数据占位符——它只应存在于 app.js 首行
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "__DATA__" not in skeleton, "骨架里不得提及数据占位符（会被字符串替换误伤）"
    assert "__INSIGHT_DATA__" not in skeleton


def test_compose_document_injects_payload_once():
    """数据只注入一次：重复注入会让单文件体积翻倍（实测事故）。"""
    payload = _support.payload("full")
    doc = B.G.compose_document(payload)
    assert doc.count('"scopeLabel"') == 1, "payload 被注入了多次，体积会翻倍"
    assert doc.count("const DATA={") == 1


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


def test_app_js_has_unified_error_ui():
    """P3-03：统一错误 UI 的入口必须留在脚本里，且五类故障都要接上。

    这条是「静默失败」的防腐层——曾经 SW / Leaflet / 瓦片失败全是空 catch，
    用户只看到一片空白或离线图，不知道发生了什么、也无法重试。
    """
    js = B.G.JS_PATH.read_text(encoding="utf-8")
    for token in ("function failBar", "function dismissFail", "function reportRuntimeError",
                  "window.__MING_READY=true", "controllerchange", "tileerror",
                  "unhandledrejection", "navigator.serviceWorker.register('sw.js')"):
        assert token in js, token
    # 不允许再出现「空 catch 吞掉失败」的写法（SW 注册 / Leaflet 就绪回落）
    assert ".catch(()=>{});" not in js, "存在静默吞掉异常的 catch"
    assert js.count("failBar(") >= 5, "五类故障接入点不应少于 5 处"


def test_css_has_fail_bar_levels():
    """提示条三级样式与可打印降级（打印时不应把错误条印到纸上）。"""
    css = B.G.CSS_PATH.read_text(encoding="utf-8")
    for token in (".fail-host", ".fail-bar", ".fail-error", ".fail-warn", ".fail-info",
                  ".fail-act", ".fail-close"):
        assert token in css, token
    assert "@media print{.fail-host,.fail-bar{display:none}}" in css, "打印时必须隐藏错误条"


def test_graphics_have_alt_text():
    """P3-02：纯图形（canvas / 矩阵 / SVG 网络图）必须带 role=img 与描述性替代文本，
    否则屏幕阅读器什么也读不到——而这三张图正是报告里信息密度最高的部分。"""
    js = B.G.JS_PATH.read_text(encoding="utf-8")
    assert 'id="fullGraph" class="network-svg full-graph-canvas" role="img"' in js
    assert "aria-describedby=\"fullSummary\"" in js
    assert "canvas.setAttribute('aria-label'" in js, "canvas 的替代文本要按当前模式动态生成"
    assert 'heatmap-grid" role="img" aria-label=' in js
    assert 'class="network-svg" viewBox="0 0 ${svgWidth} ${svgHeight}" role="img"' in js


def test_skeleton_has_boot_guard():
    """骨架里的启动守卫：数据被裁剪/脚本抛错时要给出可见提示，而不是空白页。

    守卫必须独立于主脚本（单独的 <script>），否则主脚本解析失败时它也不会执行。
    """
    skeleton = B.G.TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "__MING_READY" in skeleton, "骨架应检查主脚本是否已就绪"
    assert skeleton.count("<script>") >= 2, "守卫必须是独立的一段脚本"
    assert skeleton.count("__TITLE__") == 2, "新增脚本不得引入标题占位符"
    assert skeleton.rstrip().endswith("</html>")
    # 主脚本必须真的置位这个标记，否则守卫会误报
    assert "window.__MING_READY=true" in B.G.JS_PATH.read_text(encoding="utf-8")
