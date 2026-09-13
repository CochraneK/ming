# -*- coding: utf-8 -*-
"""单文件报告的无头浏览器自检（无需 agent-browser / jsdom）。

直接调用本机 Chrome `--dump-dom`：脚本报错会导致 DOM 为空，因此断言「渲染后的
DOM 里应当出现什么」即可同时验「没崩」与「功能对」。
**注意**：产物把 JS/CSS 全内联在同一个文件里，所以断言必须用**正则匹配真实渲染出的
标签**，而不能用裸字符串——例如 'flash'、'detail-grid' 这些词在脚本源码里本来就有，
写 `in dom` 会永远为真（假通过）。

用法：python .dump/_browser_check.py [路径，默认 index.html]
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "index.html"
# as_uri() 只接受绝对路径；CI 里传的是相对路径（.ci/index.html），必须先 resolve
TARGET = TARGET.resolve()


def find_chrome():
    """优先 CHROME_BIN（CI 里指向 google-chrome），否则本机常见路径 / PATH。"""
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    for name in ("google-chrome", "chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    for cand in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ):
        if Path(cand).exists():
            return cand
    return None


CHROME = find_chrome()

CASES = [
    {
        "name": "默认首屏（无 hash）",
        "hash": "",
        "yes": [r'id="overview" class="view active"', r'class="brand"'],
        "no": [r'id="characters" class="view active"'],
    },
    {
        "name": "deep link → 人物（于谦）",
        "hash": "#view=characters&person=" + "%E4%BA%8E%E8%B0%A6",
        # flash 是 2.6s 后自摘的临时类，必须用很短的预算抓（见 budget）
        "budget": 1500,
        "yes": [r'id="characters" class="view active"', r'data-char="于谦"',
                r'class="character-card [^"]*flash"', r'id="charQuery" value="于谦"'],
        "no": [],
        "regex": [(r'<h2 id="dialogTitle">([^<]*)</h2>', None)],
    },
    {
        "name": "deep link → 事件（event-0001，弹窗）",
        "hash": "#view=events&event=event-0001",
        "yes": [r'<dialog id="detailDialog" open', r'id="dialogTitle">\S'],
        "no": [],
    },
    {
        "name": "deep link → 帝王年号（万历展开）",
        "hash": "#view=dynasty&era=" + "%E4%B8%87%E5%8E%86",
        "yes": [r'class="dynasty-seg"', r'class="dynasty-card[^"]*active"', r'万历'],
        "no": [],
    },
    {
        "name": "搜索高亮（q=王阳明 → 王守仁卡）",
        "hash": "#view=characters&q=" + "%E7%8E%8B%E9%98%B3%E6%98%8E",
        "yes": [r'<mark class="hl">', r'data-char="王守仁"', r'id="charQuery" value="王阳明"'],
        "no": [],
    },
    {
        "name": "关系视图（诱导子图提示 + 表格）",
        "hash": "#view=relations",
        "yes": [r'id="relations" class="view active"', r'class="data-table"', r'关系索引'],
        "no": [],
    },
    {
        "name": "地图视图（懒加载 Leaflet 分支）",
        "hash": "#view=map",
        "yes": [r'id="map" class="view active"', r'id="mapSubnav"'],
        "no": [],
    },
]


def dump(hash_, budget=9000):
    url = TARGET.as_uri() + hash_
    with tempfile.TemporaryDirectory() as prof:
        cmd = [
            CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions",
            "--user-data-dir=" + prof, "--virtual-time-budget=%d" % budget,
            "--dump-dom", url,
        ]
        # 容器里以 root 跑 Chrome 会拒绝启动，需要显式关沙箱
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.stdout or ""


def main():
    if not CHROME:
        print("跳过：未找到 Chrome / Chromium（可用 CHROME_BIN 指定路径）")
        return 0
    print("目标：%s（%.1f MB）" % (TARGET, TARGET.stat().st_size / 1048576))
    failures = []
    for case in CASES:
        dom = dump(case["hash"], case.get("budget", 9000))
        problems = []
        if len(dom) < 20000:
            problems.append("DOM 过短（%d 字符），脚本可能在初始化时抛错" % len(dom))
        for pat in case["yes"]:
            if not re.search(pat, dom):
                problems.append("未命中 /%s/" % pat)
        for pat in case["no"]:
            if re.search(pat, dom):
                problems.append("不应命中 /%s/" % pat)
        m = re.search(r'<button data-view="(?P<v>[a-z]+)"[^>]*aria-selected="true"', dom)
        print("%s %-32s DOM %8d 字符  tab=%s" % (
            "ok  " if not problems else "FAIL", case["name"], len(dom), m.group("v") if m else "?"))
        for p in problems:
            print("       - %s" % p)
        if problems:
            failures.append(case["name"])
    print("\n" + "=" * 60)
    print("通过 %d / 失败 %d" % (len(CASES) - len(failures), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
