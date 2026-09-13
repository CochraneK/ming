# -*- coding: utf-8 -*-
"""统一构建入口（Phase 4）。

     python src/build.py                          # 全书 → index.html（单文件）
     python src/build.py --scope p3               # 叁部 → report_p3.html
     python src/build.py --target web             # 分离资源版 → dist/full/
     python src/build.py --check                  # 只校验不落盘

职责边界：
- ``generate_report.py`` 负责数据聚合（build_scope）与模板装载（load_template）；
- ``validators.py`` 负责 payload 不变量；
- 本文件只做「调度 + 渲染 + 落盘 + 退出码」，不再包含业务逻辑。

两个 target 的差别：
- ``standalone``（默认）：CSS/JS/DATA 全部内联，产物是可直接双击打开的单文件，
  用于 GitHub Pages 发布（唯一正式交付形态）。
- ``web``：CSS/JS/DATA 拆成 ``assets/`` 外链，便于本地调试与浏览器 DevTools
  逐文件断点；数据来自同一份 payload，因此两种产物内容等价。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_report as G  # noqa: E402
import validators as V  # noqa: E402

SCOPES = ("full", "p1", "p2", "p3", "p4", "p5", "p6", "p7")
DIST_DIR = BASE / "dist"

# 单文件模板里的历史遗留：某处模板字符串多了一个反引号，发布前统一抹平
# （真正的替换在 generate_report.compose_document 里，此处只作说明锚点）。
# web target 下骨架里的两个锚点整块替换（含外层标签），需要与骨架逐字一致。
_STYLE_ANCHOR = "<style>\n/*{{INLINE_CSS}}*/</style>"
_SCRIPT_ANCHOR = "<script>\n/*{{INLINE_JS}}*/</script>"
_DATA_CONST = "const DATA=__DATA__;\n"
_INSIGHT_CONST = "const INSIGHT_DATA=__INSIGHT_DATA__;\n"


def _json_for_script(obj) -> str:
    """把 Python 对象序列化成可安全嵌进 <script> 的 JSON。

    ``</`` 必须转义，否则数据里一旦出现 ``</script>`` 会提前闭合脚本标签。
    """
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def render_standalone(payload: dict) -> str:
    """单文件形态：直接复用 generate_report 的注入实现，杜绝两套口径。"""
    return G.compose_document(payload)


def render_web(payload: dict, out_dir: Path) -> dict:
    """分离资源形态：写 index.html + assets/{app.css,app.js,data.js}。"""
    skeleton = G.TEMPLATE_PATH.read_text(encoding="utf-8")
    css = G.CSS_PATH.read_text(encoding="utf-8")
    js = G.JS_PATH.read_text(encoding="utf-8")
    for anchor, name in ((_STYLE_ANCHOR, "css"), (_SCRIPT_ANCHOR, "js")):
        if anchor not in skeleton:
            raise SystemExit("骨架缺少锚点 %s（%s 无法外链）" % (name, anchor))

    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "app.css").write_text(css, encoding="utf-8")

    body = js.replace(_DATA_CONST, "", 1).replace(_INSIGHT_CONST, "", 1)
    (assets / "app.js").write_text(body, encoding="utf-8")
    (assets / "data.js").write_text(
        "const DATA=%s;\nconst INSIGHT_DATA=%s;\n"
        % (_json_for_script(payload), _json_for_script(G.INSIGHT_PAYLOAD)),
        encoding="utf-8",
    )

    html = skeleton.replace(_STYLE_ANCHOR, '<link rel="stylesheet" href="assets/app.css">')
    html = html.replace(_SCRIPT_ANCHOR, '<script src="assets/data.js"></script>\n<script src="assets/app.js"></script>')
    html = html.replace("__TITLE__", payload["scopeLabel"])
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    return {"index.html": len(html), "assets/app.css": len(css), "assets/app.js": len(body)}


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
    return findings


def _default_out(scope: str, target: str) -> Path:
    if target == "web":
        return DIST_DIR / scope
    if scope == "full":
        return BASE / "index.html"
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
            print("      %-16s %d 字符" % (name, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
