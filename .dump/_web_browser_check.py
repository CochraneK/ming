# -*- coding: utf-8 -*-
"""V4 分离资源在线版的真实 Chrome 冒烟。"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TARGET = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/full/index.html")).resolve()


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


def chrome_dump(path: Path, hash_: str = "", budget: int = 8000) -> str:
    chrome = find_chrome()
    if not chrome:
        raise SystemExit("未找到 Chrome / Chromium")
    with tempfile.TemporaryDirectory() as prof:
        cmd = [
            chrome, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions",
            "--allow-file-access-from-files", "--user-data-dir=" + prof,
            "--virtual-time-budget=%d" % budget, "--dump-dom", path.as_uri() + hash_,
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not r.stdout:
            raise AssertionError("Chrome 未返回 DOM：%s" % (r.stderr or "").strip()[-500:])
        return r.stdout


def assert_has(dom: str, *patterns: str):
    for pattern in patterns:
        if not re.search(pattern, dom, re.S):
            raise AssertionError("缺少渲染结果：%s" % pattern)


def check_home():
    dom = chrome_dump(TARGET)
    assert_has(
        dom,
        r'<button type="button" class="command-trigger"',
        r'<section class="v3-story panel"',
        r'地点已定位',
        r'事件可纪年',
    )
    print("ok   split web 首页 + V3 增强层")


def check_command_palette():
    doc = TARGET.read_text(encoding="utf-8")
    probe = """<script>
setTimeout(function(){
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true}));
  var i=document.getElementById('commandInput');
  if(i){i.value='于谦';i.dispatchEvent(new Event('input',{bubbles:true}));}
},120);
</script>\n"""
    probe_path = TARGET.parent / ".v4-command-probe.html"
    try:
        probe_path.write_text(doc.replace("</body>", probe + "</body>", 1), encoding="utf-8")
        dom = chrome_dump(probe_path, budget=8500)
    finally:
        probe_path.unlink(missing_ok=True)
    assert_has(dom, r'<div id="commandPalette" class="command-shell">', r'<strong>于谦</strong>')
    print("ok   split web Ctrl+K → 于谦")


def check_graph_reader():
    dom = chrome_dump(TARGET, "#view=visuals&net=full", 9500)
    assert_has(
        dom,
        r'id="visuals" class="view active"',
        r'<div class="v3-graph-reader" data-mode="full"[^>]*>',
        r'人物总图怎么读',
        r'data-v3-node-search',
    )
    print("ok   split web 人物总图阅读器")


if __name__ == "__main__":
    if not TARGET.exists():
        raise SystemExit("目标文件不存在：%s" % TARGET)
    check_home()
    check_command_palette()
    check_graph_reader()
