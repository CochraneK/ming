# -*- coding: utf-8 -*-
"""统一构建入口（Phase 4 / V8 双交付 + 人物详情二级按需数据）。

     python src/build.py                          # 全书 → standalone.html（单文件）
     python src/build.py --scope p3               # 叁部 → report_p3.html
     python src/build.py --target web             # 分离资源版 → dist/full/
     python src/build.py --check                  # 只校验不落盘

职责边界：
- ``generate_report.py`` 负责数据聚合（build_scope）与模板装载（load_template）；
- ``validators.py`` 负责 payload 不变量；
- 本文件只做「调度 + 渲染 + 落盘 + 退出码」，不再包含业务逻辑。

两个 target 的差别：
- ``standalone``（默认）：CSS/JS/DATA 全部内联，产物是可直接双击打开的单文件；
- ``web``：项目 CSS/JS 分离，DATA 由同一最终 payload 拆成 boot + search + 领域 chunk。
  V8 再把人物域拆成轻量 ``characters`` 卡片索引与 ``character-details`` 详情补丁；
  人物列表 / 年谱不再为单个详情提前下载完整人物关系与上下文。
"""

from __future__ import annotations

import argparse
import copy
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
DATA_LOADER_JS_PATH = BASE / "web" / "js" / "data-loader.js"
LAZY_DATA_JS_PATH = BASE / "web" / "js" / "lazy-data.js"

# 首页 + 分布视图直接消费的轻量字段。分类枚举 / 年号也很小，放进 boot 后可让
# 「分布」完全零额外请求，并让图谱/时间视图少依赖一个小块。
WEB_BOOT_KEYS = (
    "scope", "scopeLabel", "metrics", "cleaning", "distribution",
    "reigns", "eraByPart", "eventCategories", "relationCategories",
)

# characters 顶层字段在 V8 是唯一的传输级例外：列表/卡片所需字段先进入
# data-characters.js，完整详情以 name -> patch 的形式进入 data-character-details.js。
# 其它最终模型顶层字段仍只属于一个领域块，避免按页面复制数据。
WEB_CHUNK_FIELDS = {
    "characters": ("aliasIndex", "chapters", "quotes"),
    "events": ("events",),
    "space": ("locations", "chapterLocations", "voyages"),
    "relations": ("relations", "endpointKinds", "relationScope"),
    "time": ("timeline", "unknownTimeline", "lifespans"),
    "graphs": ("visualizations", "relationGraphFull", "relationGraphEntities"),
    "insight": ("insightIndex",),
    "meta": ("model",),
}
WEB_CHUNKS = (
    "characters", "character-details", "events", "space", "relations",
    "time", "graphs", "insight", "meta",
)

# 人物列表和打印卡真正读取的字段。events/contextEvents 只需前三项作卡片摘要；
# profile 只保留 cleanCardFields() 在卡面使用的 label/origin/note。打开详情时再
# 用 character-details 中的完整字段覆盖，最终对象与 generate_report 输出逐值一致。
CHARACTER_CARD_KEYS = (
    "name", "faction", "role", "life", "aliases", "chapters", "summary", "status",
)
CHARACTER_CARD_PROFILE_KEYS = ("label", "origin", "note")

_STYLE_ANCHOR = "<style>\n/*{{INLINE_CSS}}*/</style>"
_SCRIPT_ANCHOR = "<script>\n/*{{INLINE_JS}}*/</script>"
_DATA_CONST = "const DATA=__DATA__;\n"
_INSIGHT_CONST = "const INSIGHT_DATA=__INSIGHT_DATA__;\n"


def _json_for_script(obj) -> str:
    """把 Python 对象序列化成紧凑、可安全嵌进 <script> 的 JSON。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def split_character_transport(characters: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """把人物对象拆成卡片摘要 + 详情补丁；应用补丁后必须逐值恢复原对象。"""
    summaries = []
    details = {}
    for character in characters:
        summary = {
            key: copy.deepcopy(character[key])
            for key in CHARACTER_CARD_KEYS
            if key in character
        }
        summary["events"] = copy.deepcopy((character.get("events") or [])[:3])
        summary["contextEvents"] = copy.deepcopy((character.get("contextEvents") or [])[:3])
        profile = character.get("profile")
        if isinstance(profile, dict):
            summary["profile"] = {
                key: copy.deepcopy(profile[key])
                for key in CHARACTER_CARD_PROFILE_KEYS
                if key in profile
            }

        detail = {
            key: copy.deepcopy(value)
            for key, value in character.items()
            if key not in summary or summary[key] != value
        }
        name = str(character.get("name") or "")
        if not name:
            raise SystemExit("V8 人物详情拆分遇到空姓名")
        summaries.append(summary)
        details[name] = detail
    return summaries, details


def split_web_chunks(payload: dict) -> tuple[dict, dict[str, dict]]:
    """把最终 DATA 无损变换成 boot + 领域块；人物详情采用可逆补丁。"""
    boot = {key: payload[key] for key in WEB_BOOT_KEYS if key in payload}

    # app.js 启动阶段会立即访问这几项；用空壳保证首页可启动，后续领域块覆盖它们。
    boot.update({
        "characters": [],
        "locations": [],
        "events": [],
        "relations": [],
        "chapters": {},
    })

    # 首页数据故事只需一个最高连接入口，不值得首访加载完整 200+ KiB 人物图。
    nodes = list((payload.get("relationGraphFull") or {}).get("nodes") or [])
    hub = max(nodes, key=lambda x: (x.get("degree", 0), x.get("name", "")), default=None)
    boot["relationGraphFull"] = {
        "nodes": ([{"name": hub.get("name"), "degree": hub.get("degree", 0)}] if hub else []),
        "links": [],
    }

    summaries, details = split_character_transport(payload.get("characters") or [])
    chunks: dict[str, dict] = {
        "characters": {
            **{key: payload[key] for key in WEB_CHUNK_FIELDS["characters"] if key in payload},
            "characters": summaries,
        },
        "character-details": {"details": details},
    }
    claimed = set(WEB_BOOT_KEYS) | {"characters"}
    claimed.update(WEB_CHUNK_FIELDS["characters"])

    for name, fields in WEB_CHUNK_FIELDS.items():
        if name == "characters":
            continue
        chunk = {}
        for key in fields:
            if key in payload:
                chunk[key] = payload[key]
                claimed.add(key)
        chunks[name] = chunk

    unknown = sorted(set(payload) - claimed)
    if unknown:
        raise SystemExit("V8 未分配的最终 payload 字段：%s" % ", ".join(unknown))
    return boot, chunks


def reconstruct_web_payload(boot: dict, chunks: dict[str, dict]) -> dict:
    """Python 侧模拟浏览器加载全部 V8 chunk，验证传输变换严格可逆。"""
    merged = copy.deepcopy(boot)
    for name in WEB_CHUNKS:
        if name == "character-details":
            continue
        merged.update(copy.deepcopy(chunks[name]))

    details = (chunks.get("character-details") or {}).get("details") or {}
    for character in merged.get("characters") or []:
        character.update(copy.deepcopy(details.get(character.get("name"), {})))
    return merged


def build_search_index(payload: dict) -> dict:
    """从最终模型派生轻量命令搜索目录；只保留检索/展示字段，不复制详情对象。"""
    rows = []
    for x in payload.get("characters") or []:
        p = x.get("profile") or {}
        aliases = [str(v) for v in (x.get("aliases") or []) if v]
        factions = [str(v) for v in (p.get("factions") or []) if v]
        orgs = [str(v) for v in (p.get("orgs") or []) if v]
        title = str(x.get("name") or "")
        role = str(x.get("role") or "")
        life = str(x.get("life") or "")
        faction = str(x.get("faction") or "")
        search = " ".join(v for v in [title, *aliases, role, faction, *factions, *orgs] if v).lower()
        meta = " · ".join(v for v in [role, "、".join(factions), life] if v)
        rows.append({"kind": "person", "id": title, "title": title, "meta": meta, "search": search})

    for x in payload.get("locations") or []:
        title = str(x.get("ancient") or "")
        modern = str(x.get("modern") or "")
        region = str(x.get("region") or "")
        aliases = [str(v) for v in (x.get("altNames") or []) if v]
        search = " ".join(v for v in [title, modern, region, *aliases] if v).lower()
        meta = " · ".join(v for v in [modern, region] if v)
        rows.append({"kind": "place", "id": title, "title": title, "meta": meta, "search": search})

    for x in payload.get("events") or []:
        event_id = str(x.get("id") or "")
        title = str(x.get("name") or "")
        year = str(x.get("year") or "年份待考")
        category = str(x.get("category") or "")
        event_type = str(x.get("type") or "")
        location = str(x.get("location") or "")
        participants = [str(v) for v in (x.get("participants") or []) if v]
        search = " ".join(v for v in [title, year, category, event_type, location, *participants] if v).lower()
        meta = " · ".join(v for v in [year, category, location] if v)
        rows.append({"kind": "event", "id": event_id, "title": title, "meta": meta, "search": search})
    return {"rows": rows}


def _chunk_script(name: str, data: dict) -> str:
    """生成领域块脚本；人物详情块写入补丁仓，insight 块同时携带 INSIGHT_DATA。"""
    if name == "character-details":
        body = (
            "window.__MING_CHARACTER_DETAILS__=Object.assign(window.__MING_CHARACTER_DETAILS__||{},%s);\n"
            "if(window.__MING_APPLY_CHARACTER_DETAILS__)window.__MING_APPLY_CHARACTER_DETAILS__();\n"
            % _json_for_script(data.get("details") or {})
        )
    else:
        body = "Object.assign(DATA,%s);\n" % _json_for_script(data)
    insight = "Object.assign(INSIGHT_DATA,%s);\n" % _json_for_script(G.INSIGHT_PAYLOAD) if name == "insight" else ""
    return (
        body + insight +
        "window.__MING_DATA_CHUNKS__=window.__MING_DATA_CHUNKS__||{};\n"
        "window.__MING_DATA_CHUNKS__[%s]=true;\n"
        "document.dispatchEvent(new CustomEvent('ming:data-chunk',{detail:{name:%s}}));\n"
        % (json.dumps(name), json.dumps(name))
    )


def _externalize_generated_block(source: str, *, tag: str, generated_from: str, replacement: str) -> str:
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
    return G.compose_document(payload)


def render_web(payload: dict, out_dir: Path) -> dict:
    """在线形态：HTML/CSS/JS 分离，DATA 按 boot/search/领域块/人物详情按需交付。"""
    skeleton = G.TEMPLATE_PATH.read_text(encoding="utf-8")
    css = G.CSS_PATH.read_text(encoding="utf-8")
    js = G.JS_PATH.read_text(encoding="utf-8")
    theme_css = THEME_CSS_PATH.read_text(encoding="utf-8")
    experience_css = EXPERIENCE_CSS_PATH.read_text(encoding="utf-8")
    experience_js = EXPERIENCE_JS_PATH.read_text(encoding="utf-8")
    data_loader_js = DATA_LOADER_JS_PATH.read_text(encoding="utf-8")
    lazy_data_js = LAZY_DATA_JS_PATH.read_text(encoding="utf-8")

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
        "data-loader.js": data_loader_js,
        "lazy-data.js": lazy_data_js,
    }
    for name, content in files.items():
        (assets / name).write_text(content, encoding="utf-8")

    body = js.replace(_DATA_CONST, "", 1).replace(_INSIGHT_CONST, "", 1)
    (assets / "app.js").write_text(body, encoding="utf-8")

    boot_payload, chunks = split_web_chunks(payload)
    search_index = build_search_index(payload)
    boot_js = (
        "const DATA=%s;\n"
        "const INSIGHT_DATA={\"sections\":[],\"refs\":[]};\n"
        "window.__MING_DATA_CHUNKS__={};\n"
        "window.__MING_CHARACTER_DETAILS__={};\n"
        % _json_for_script(boot_payload)
    )
    search_js = (
        "window.__MING_SEARCH_INDEX__=%s;\n"
        "window.__MING_SEARCH_INDEX_READY=true;\n"
        "document.documentElement.dataset.mingSearch='ready';\n"
        "document.dispatchEvent(new CustomEvent('ming:search-index'));\n"
        % _json_for_script(search_index)
    )
    (assets / "boot-data.js").write_text(boot_js, encoding="utf-8")
    (assets / "search-index.js").write_text(search_js, encoding="utf-8")

    chunk_scripts = {}
    for name in WEB_CHUNKS:
        content = _chunk_script(name, chunks[name])
        chunk_scripts[name] = content
        (assets / ("data-%s.js" % name)).write_text(content, encoding="utf-8")

    sw_bytes = SW_PATH.read_bytes()
    (out_dir / "sw.js").write_bytes(sw_bytes)

    html = skeleton.replace(_STYLE_ANCHOR, '<link rel="stylesheet" href="assets/app.css">')
    html = _externalize_generated_block(
        html, tag="style", generated_from="web/css/theme.css",
        replacement='<link rel="stylesheet" href="assets/theme.css">',
    )
    html = _externalize_generated_block(
        html, tag="style", generated_from="web/css/experience.css",
        replacement='<link rel="stylesheet" href="assets/experience.css">',
    )
    html = html.replace(
        _SCRIPT_ANCHOR,
        '<script src="assets/boot-data.js"></script>\n'
        '<script src="assets/data-loader.js"></script>\n'
        '<script src="assets/app.js"></script>\n'
        '<script src="assets/lazy-data.js"></script>',
    )
    html = _externalize_generated_block(
        html, tag="script", generated_from="web/js/experience.js",
        replacement='<script src="assets/experience.js"></script>',
    )
    html = html.replace("__TITLE__", payload["scopeLabel"])
    (out_dir / "index.html").write_text(html, encoding="utf-8")

    written = {
        "index.html": len(html),
        "assets/app.css": len(css),
        "assets/theme.css": len(theme_css),
        "assets/experience.css": len(experience_css),
        "assets/app.js": len(body),
        "assets/boot-data.js": len(boot_js),
        "assets/search-index.js": len(search_js),
        "assets/data-loader.js": len(data_loader_js),
        "assets/lazy-data.js": len(lazy_data_js),
        "assets/experience.js": len(experience_js),
        "sw.js": len(sw_bytes),
    }
    for name, content in chunk_scripts.items():
        written["assets/data-%s.js" % name] = len(content)
    return written


def check_render(payload: dict, findings: list) -> list:
    doc = render_standalone(payload)
    for token in ("__DATA__", "__INSIGHT_DATA__", "__TITLE__"):
        if token in doc:
            findings.append(V.Finding(V.ERROR, "V-TPL-01", "渲染后仍残留占位符 %s" % token))
    if "const DATA=" not in doc:
        findings.append(V.Finding(V.ERROR, "V-TPL-02", "渲染结果里找不到 DATA 注入点"))
    if not doc.rstrip().endswith("</html>"):
        findings.append(V.Finding(V.ERROR, "V-TPL-03", "渲染结果未正常闭合 </html>"))
    if len(doc) < 500_000:
        findings.append(V.Finding(V.WARNING, "V-TPL-04", "渲染结果仅 %d 字符，远小于历史规模，可能数据缺失" % len(doc)))
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
        print("[3/3] V8 人物详情二级按需资源已生成 %s" % out)
        for name, size in written.items():
            print("      %-28s %d 字节/字符" % (name, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
