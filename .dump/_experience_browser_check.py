# -*- coding: utf-8 -*-
"""V3 产品体验层的真实浏览器冒烟：首页叙事、快捷搜索、图谱阅读器。"""
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
    # 产物把组件 HTML 模板字符串内联在 <script> 中；先剥掉源码，避免字符串断言假通过。
    dom = re.sub(r"<script\b[^>]*>.*?</script>", "", dom, flags=re.I | re.S)
    dom = re.sub(r"<style\b[^>]*>.*?</style>", "", dom, flags=re.I | re.S)
    return dom


def assert_has(dom: str, *patterns: str):
    for p in patterns:
        if not re.search(p, dom, re.S):
            raise AssertionError("缺少渲染结果：%s" % p)


def check_home():
    dom = rendered_only(chrome_dump(TARGET))
    assert_has(
        dom,
        r'<button type="button" class="command-trigger"[^>]*aria-controls="commandPalette"',
        r'<section class="v3-story panel"[^>]*aria-labelledby="v3StoryTitle"',
        r'id="v3StoryTitle">先读懂这份知识图谱，再进入细节',
        r'地点已定位', r'事件可纪年',
    )
    print("ok   V3 首页叙事 + 全局搜索入口")


def check_command_palette():
    doc = TARGET.read_text(encoding="utf-8")
    probe = """<script>
setTimeout(function(){
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true}));
  var i=document.getElementById('commandInput');
  if(i){i.value='于谦';i.dispatchEvent(new Event('input',{bubbles:true}));}
},80);
</script>\n"""
    if "</body>" not in doc:
        raise AssertionError("产物缺少 </body>")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "probe.html"
        p.write_text(doc.replace("</body>", probe + "</body>", 1), encoding="utf-8")
        dom = rendered_only(chrome_dump(p, budget=7500))
    assert_has(
        dom,
        r'<div id="commandPalette" class="command-shell">',
        r'<button type="button" role="option"[^>]*class="command-item active"',
        r'<strong>于谦</strong>',
        r'<span class="command-kind">人物</span>',
    )
    print("ok   Ctrl+K 全局搜索 → 于谦")


def check_graph_reader():
    dom = rendered_only(chrome_dump(TARGET, "#view=visuals&net=full", 9000))
    assert_has(
        dom,
        r'<div class="v3-graph-reader" data-mode="full">',
        r'人物总图怎么读',
        r'data-v3-node-search',
        r'高连接入口',
        r'data-v3-focus=',
        r'只突出一跳邻域',
    )
    print("ok   人物总图阅读器 + 邻域聚焦入口")


if __name__ == "__main__":
    if not TARGET.exists():
        raise SystemExit("目标文件不存在：%s" % TARGET)
    check_home()
    check_command_palette()
    check_graph_reader()
