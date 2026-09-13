# -*- coding: utf-8 -*-
"""统一构建入口（Phase 4 / V4 双交付）。

     python src/build.py                          # 全书 → standalone.html（单文件）
     python src/build.py --scope p3               # 叁部 → report_p3.html
     python src/build.py --target web             # 分离资源版 → dist/full/
     python src/build.py --check                  # 只校验不落盘

职责边界：
- ``generate_report.py`` 负责数据聚合（build_scope）与模板装载（load_template）；
- ``validators.py`` 负责 payload 不变量；
- 本文件只做「调度 + 渲染 + 落盘 + 退出码」，不再包含业务逻辑。

两个 target 的差别：
- ``standalone``（默认）：CSS/JS/DATA 全部内联，产物是可直接双击打开的单文件，
  作为离线携带 / 归档版本；默认全书文件名为 ``standalone.html``，避免误覆盖在线入口；
- ``web``：基础样式、主题、体验层、业务 JS 与 DATA 全部拆进 ``assets/``，
  用于在线发布和浏览器缓存。两种产物来自同一份 payload，内容等价。
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
import validators as V  # noqa: E402

SCOPES = ("full", "p1", "p2", "p3", "p4", "p5", "p6", "p7")
DIST_DIR = BASE / "dist"
SW_PATH = BASE / "sw.js"
THEME_CSS_PATH = BASE / "web" / "css" / "theme.css"
EXPERIENCE_CSS_PATH = BASE / "web" / "css" / "experience.css"
EXPERIENCE_JS_PATH = BASE / "web" / "js" / "experience.js"

# web target 下骨架里的两个主锚点整块替换（含外层标签），需要与骨架逐字一致。
_STYLE_ANCHOR = "<style>\n/*{{INLINE_CSS}}*/</style>"
_SCRIPT_ANCHOR = "<script>\n/*{{INLINE_JS}}*/</script>"
_DATA_CONST = "const DATA=__DATA__;\n"
_INSIGHT_CONST = "const INSIGHT_DATA=__INSIGHT_DATA__;\n"


def _json_for_script(obj) -> str:
    """把 Python 对象序列化成可安全嵌进 <script> 的 JSON。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _externalize_generated_block(source: str, *, tag: str, generated_from: str, replacement: str) -> str:
    """把模板里的生成镜像块替换成外链，且要求恰好命中一次。"""
    pattern = re.compile(
        r'<%s\s+data-generated-from="%s">.*?</%s>'
        % (tag, re.escape(generated_from), tag),
        re.DOTALL,
    )
    updated, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise SystemExit("web target 找不到唯一生成镜像块：%s" % generated_from)
    return updated


def render_standalone(payload: dict) -> str:
    """单文件形态：直接复用 generate_report 的注入实现，杜绝两套口径。"""
    return G.compose_document(payload)


def render_web(payload: dict, out_dir: Path) -> dict:
    """分离资源形态：HTML 只保留骨架，所有项目 CSS/JS/DATA 均写入 assets/。"""
    skeleton = G.TEMPLATE_PATH.read_text(encoding="utf-8")
    css = G.CSS_PATH.read_text(encoding="utf-8")
    js = G.JS_PATH.read_text(encoding="utf-8")
    theme_css = THEME_CSS_PATH.read_text(encoding="utf-8")
    experience_css = EXPERIENCE_CSS_PATH.read_text(encoding="utf-8")
    experience_js = EXPERIENCE_JS_PATH.read_text(encoding="utf-8")

    for anchor, name in ((_STYLE_ANCHOR, "css"), (_SCRIPT_ANCHOR, "js")):
        if anchor not in skeleton:
            raise SystemExit("骨架缺少锚点 %s（%s 无法外链）" % (name, anchor))

    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    files = {
        "app.css": css,
        "theme.css": theme_css,
        "experience.css": experience_css,
        "experience.js": experience_js,
    }
    for name, content in files.items():
        (assets / name).write_text(content, encoding="utf-8")

    body = js.replace(_DATA_CONST, "", 1).replace(_INSIGHT_CONST, "", 1)
    (assets / "app.js").write_text(body, encoding="utf-8")
    data_js = (
        "const DATA=%s;\nconst INSIGHT_DATA=%s;\n"
        % (_json_for_script(payload), _json_for_script(G.INSIGHT_PAYLOAD))
    )
    (assets / "data.js").write_text(data_js, encoding="utf-8")

    # app.js 注册的是相对于页面根目录的 sw.js。这里必须按 bytes 原样复制：
    # read_text/write_text 会把 CRLF 规范化成 LF，使发布工作流的逐字节一致性检查误报。
    sw_bytes = SW_PATH.read_bytes()
    (out_dir / "sw.js").write_bytes(sw_bytes)

    html = skeleton.replace(_STYLE_ANCHOR, '<link rel="stylesheet" href="assets/app.css">')
    html = _externalize_generated_block(
        html,
        tag="style",
        generated_from="web/css/theme.css",
        replacement='<link rel="stylesheet" href="assets/theme.css">',
    )
    html = _externalize_generated_block(
        html,
        tag="style",
        generated_from="web/css/experience.css",
        replacement='<link rel="stylesheet" href="assets/experience.css">',
    )
    html = html.replace(
        _SCRIPT_ANCHOR,
        '<script src="assets/data.js"></script>\n<script src="assets/app.js"></script>',
    )
    html = _externalize_generated_block(
        html,
        tag="script",
        generated_from="web/js/experience.js",
        replacement='<script src="assets/experience.js"></script>',
    )
    html = html.replace("__TITLE__", payload["scopeLabel"])
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    return {
        "index.html": len(html),
        "assets/app.css": len(css),
        "assets/theme.css": len(theme_css),
        "assets/experience.css": len(experience_css),
        "assets/app.js": len(body),
        "assets/data.js": len(data_js),
        "assets/experience.js": len(experience_js),
        "sw.js": len(sw_bytes),
    }


def check_render(payload: dict, findings: list) -> list:
    """渲染层自检：锚点是否齐全、替换后是否残留占位符。"""
    doc = render_standalone(payload)
    for token in ("__DATA__", "__INSIGHT_DATA__", "__TITLE__"):
        if token in doc:
            findings.append(V.Finding(V.ERROR, "V-TPL-01", "渲染后仍残留占位符 %s" % token))
    if "const DATA=" not in doc:
        findings.append(V.Finding(V.ERROR, "V-TPL-02", "渲染结果里找不到 DATA 注入点"))
    if not doc.rstrip().endswith("</html>"):
        findings.append(V.Finding(V.ERROR, "V-TPL-03", "渲染结果未正常闭合 </html>"))
    if len(doc) < 500_000:
        findings.append(
            V.Finding(V.WARNING, "V-TPL-04", "渲染结果仅 %d 字符，远小于历史规模，可能数据缺失" % len(doc))
        )
    skeleton = G.TEMPLATE_PATH.read_text(encoding="utf-8")
    for anchor in (_STYLE_ANCHOR, _SCRIPT_ANCHOR):
        if anchor not in skeleton:
            findings.append(V.Finding(V.ERROR, "V-TPL-05", "骨架缺少锚点：%s" % anchor))
    for generated_from in ("web/css/theme.css", "web/css/experience.css", "web/js/experience.js"):
        if ('data-generated-from="%s"' % generated_from) not in skeleton:
            findings.append(V.Finding(V.ERROR, "V-TPL-06", "骨架缺少生成镜像块：%s" % generated_from))
    return findings


def _default_out(scope: str, target: str) -> Path:
    if target == "web":
        return DIST_DIR / scope
    if scope == "full":
        return BASE / "standalone.html"
    return BASE / ("report_%s.html" % scope)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="明朝知识报告统一构建入口")
    parser.add_argument("--scope", choices=SCOPES, default="full", help="构建范围，默认全书")
    parser.add_argument("--target", choices=("standalone", "web"), default="standalone", help="产物形态")
    parser.add_argument("--out", type=Path, default=None, help="覆盖输出路径（文件或目录）")
    parser.add_argument("--check", action="store_true", help="只做校验与内存渲染，不写任何文件")
    parser.add_argument("--json", type=Path, default=None, help="把校验结论写成 JSON")
    parser.add_argument("--quiet", action="store_true", help="只打印一行结论")
    args = parser.parse_args(argv)

    payload = G.build_scope(args.scope)
    metrics = " · ".join("%s %s" % (k, v) for k, v in payload["metrics"].items())
    if not args.quiet:
        print("[1/3] 数据聚合完成：%s" % metrics)

    findings = V.validate_payload(payload)
    findings = check_render(payload, findings)
    findings = V.sort_findings(findings)
    counts = V.count_by_severity(findings)
    if args.json:
        V.write_json(findings, args.json)
    if not args.quiet:
        print("[2/3] %s" % V.format_report(findings, "scope=%s target=%s" % (args.scope, args.target)))
    else:
        print("校验：ERROR %d / WARNING %d / INFO %d" % (counts[V.ERROR], counts[V.WARNING], counts[V.INFO]))

    if V.has_errors(findings):
        print("[!] 存在 ERROR，已中止构建（数据自相矛盾，不要发布）", file=sys.stderr)
        return 2

    if args.check:
        print("[3/3] --check：未写入任何文件")
        return 0

    out = args.out or _default_out(args.scope, args.target)
    if args.target == "standalone":
        out.parent.mkdir(parents=True, exist_ok=True)
        doc = render_standalone(payload)
        out.write_text(doc, encoding="utf-8")
        print("[3/3] 单文件已生成 %s（%d 字符 / %.1f MB）" % (out, len(doc), out.stat().st_size / 1048576))
    else:
        out.mkdir(parents=True, exist_ok=True)
        written = render_web(payload, out)
        print("[3/3] 分离资源已生成 %s" % out)
        for name, size in written.items():
            print("      %-24s %d 字节/字符" % (name, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
