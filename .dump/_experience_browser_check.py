# -*- coding: utf-8 -*-
"""Classic UI 真实浏览器冒烟：旧导航/旧首页/图谱仍可用，V2/V3 覆盖层不再出现。"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TARGET = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path("index.html")).resolve()


def find_chrome():
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    for name in ("google-chrome", "chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    for cand in ("/usr/bin/google-chrome", "/usr/bin/chromium"):
        if Path(cand).exists():
            return cand
    return None


def chrome_dump(path: Path, hash_: str = "", budget: int = 7000) -> str:
    chrome = find_chrome()
    if not chrome:
        raise SystemExit("未找到 Chrome / Chromium")
    with tempfile.TemporaryDirectory() as prof:
        cmd = [
            chrome, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions",
            "--user-data-dir=" + prof, "--virtual-time-budget=%d" % budget,
            "--dump-dom", path.as_uri() + hash_,
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not r.stdout:
            raise AssertionError("Chrome 未返回 DOM：%s" % (r.stderr or "").strip()[-500:])
        return r.stdout


def rendered_only(dom: str) -> str:
    dom = re.sub(r"<script\b[^>]*>.*?</script>", "", dom, flags=re.I | re.S)
    dom = re.sub(r"<style\b[^>]*>.*?</style>", "", dom, flags=re.I | re.S)
    return dom


def assert_has(dom: str, *patterns: str):
    for p in patterns:
        if not re.search(p, dom, re.S):
            raise AssertionError("缺少渲染结果：%s" % p)


def assert_not_has(dom: str, *patterns: str):
    for p in patterns:
        if re.search(p, dom, re.S):
            raise AssertionError("经典 UI 不应出现：%s" % p)


def check_home():
    dom = rendered_only(chrome_dump(TARGET))
    for label in ("总览", "分布", "图谱", "地点", "地图", "人物", "事件", "关系", "时间轴", "帝王", "年谱", "洞察"):
        assert_has(dom, r'<button data-view="[^"]+"[^>]*>' + label + r'</button>')
    assert_has(dom, r'class="summary-hero"', r'class="metric-grid"')
    assert_not_has(dom, r'class="nav-cluster"', r'class="v3-story', r'class="command-trigger"')
    print("ok   Classic UI 首页 + 原 12 视图导航")


def check_no_command_overlay():
    doc = TARGET.read_text(encoding="utf-8")
    probe = """<script>
setTimeout(function(){
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true}));
},80);
</script>\n"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "probe.html"
        p.write_text(doc.replace("</body>", probe + "</body>", 1), encoding="utf-8")
        dom = rendered_only(chrome_dump(p, budget=7500))
    assert_not_has(dom, r'id="commandPalette"', r'class="command-shell"')
    print("ok   Classic UI 不注入命令面板")


def check_graph_view_without_reader_overlay():
    dom = rendered_only(chrome_dump(TARGET, "#view=visuals&net=full", 9000))
    assert_has(dom, r'id="visuals"[^>]*class="view active"', r'class="full-graph-canvas"')
    assert_not_has(dom, r'class="v3-graph-reader"', r'data-v3-node-search')
    print("ok   原图谱视图可用且无 V3 reader 覆盖层")


if __name__ == "__main__":
    if not TARGET.exists():
        raise SystemExit("目标文件不存在：%s" % TARGET)
    check_home()
    check_no_command_overlay()
    check_graph_view_without_reader_overlay()
