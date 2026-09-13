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
import time
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
    {
        "name": "图谱 · 实体图（net=entity，含类型图例）",
        "hash": "#view=visuals&net=entity",
        # 注意：Chrome --dump-dom 把布尔属性序列化成 `selected=""`，不能写成 `selected>`
        "yes": [r'id="visuals" class="view active"',
                r'<option value="entity" selected="">',
                r'id="netModeNote">实体图口径',
                r'实体关系图：<strong>\d+</strong> 个实体',
                # 实体图模式必须显示总图、隐藏中心人物邻域，不能两块同时出现
                r'id="egoNet" style="display:none"',
                r'id="fullNet" style="display:block"',
                # 无障碍：canvas 必须带描述性替代文本（P3-02），且按模式取不同口径
                r'<canvas id="fullGraph"[^>]*role="img"[^>]*aria-describedby="fullSummary"',
                r'aria-label="全书实体关系图：\d+ 个实体、\d+ 条关系'],
        "no": [r'id="fullSummary"><span>人物关系图'],
        # 图例内容必须「限定在图例元素内」断言：产物内联了 JS 源码，
        # 全局搜 'kind-dot' 会命中源码里的模板字符串（永久假通过/假失败）。
        "scoped": [
            {"label": "类型图例（fullLegend）", "anchor": r'id="fullLegend"', "size": 600,
             "yes": [r'kind-dot', r'节点类型', r'人物 \d+', r'(地点|机构|政权|其他) \d+'], "no": []},
        ],
    },
    {
        "name": "图谱 · 人物图（net=full，方案 A 口径）",
        "hash": "#view=visuals&net=full",
        "yes": [r'<option value="full" selected="">',
                r'id="netModeNote">人物图口径',
                r'人物关系图：<strong>\d+</strong> / \d+ 人',
                r'id="egoNet" style="display:none"',
                r'id="fullNet" style="display:block"',
                r'aria-label="全书人物关系图：\d+ 人、\d+ 条人物关系'],
        "no": [],
        "scoped": [
            {"label": "图例不应含类型色点（fullLegend）", "anchor": r'id="fullLegend"', "size": 600,
             "yes": [r'cat-dot'], "no": [r'kind-dot']},
        ],
    },
    {
        "name": "时间轴区间（from/to 预填 + 过滤生效）",
        "hash": "#view=timeline&from=1400&to=1450",
        "yes": [r'id="timeline" class="view active"',
                r'id="timelineFrom"[^>]*value="1400"',
                r'id="timelineTo"[^>]*value="1450"',
                r'当前筛选 1400—1450 年（命中 \d+ / \d+ 件）'],
        "no": [],
    },
    {
        "name": "洞察联动 · 正文实体可点击",
        "hash": "#view=insight",
        # ins-link 由 linkifyInsight() 在渲染后插入 DOM，必须匹配真实渲染出的 button 标签
        "yes": [r'id="insight" class="view active"',
                r'<button class="ins-link ins-p"[^>]*data-ins-p="',
                r'<button class="ins-link ins-l"[^>]*data-ins-l="'],
        "no": [],
    },
    {
        "name": "洞察联动 · 详情页反向入口（王守仁）",
        "hash": "#view=characters&person=%E7%8E%8B%E5%AE%88%E4%BB%81&detail=1",
        "yes": [r'<dialog id="detailDialog" open', r'相关洞察', r'class="ins-chip"[^>]*data-ins-goto="'],
        "no": [],
    },
    {
        "name": "地点卡 · 别称与书中提及分级（宁远）",
        # 缺陷回归闸：mentioned_as 里混着「熊廷弼不守、努尔哈赤退兵错过之关键据点」这类
        # 说明片段，原先统一挂在「别称」下展示。现在必须拆成两块，且描述不许出现在别称里。
        "hash": "#view=locations&place=%E5%AE%81%E8%BF%9C",
        "yes": [r'<dialog id="detailDialog" open', r'id="dialogTitle">宁远',
                r'<strong>别称</strong>',
                r'<strong>书中提及（\d+）</strong>',
                r'袁崇焕驻守'],
        "no": [r'别称</strong><p>[^<]*熊廷弼', r'别称</strong><p>[^<]*袁崇焕'],
    },

]


def check_boot_guard():
    """故意制造语法错误，验证骨架里的启动守卫确实会渲染出可见错误条。

    产物把 JS 内联在同一文件里，所以不能只断言 'fail-bar' 出现在源码里；
    必须匹配守卫运行时真实拼出来的 DOM 属性（class + role）。
    """
    if not TARGET.exists():
        print("跳过启动守卫自检：目标文件不存在")
        return 0
    doc = TARGET.read_text(encoding="utf-8")
    # 在主脚本里插一条语法错误：整段 <script> 解析失败 → 主脚本一行都不执行
    poisoned = doc.replace("const REL_CAT_COLORS=", "const __BROKEN__=;const REL_CAT_COLORS=", 1)
    if poisoned == doc:
        print("FAIL 启动守卫自检：未找到注入点 const REL_CAT_COLORS=")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "index.html"
        broken.write_text(poisoned, encoding="utf-8")
        with tempfile.TemporaryDirectory() as prof:
            cmd = [
                CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                "--no-default-browser-check", "--disable-extensions",
                "--user-data-dir=" + prof, "--virtual-time-budget=9000",
                "--dump-dom", broken.as_uri(),
            ]
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                cmd.insert(1, "--no-sandbox")
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            dom = r.stdout or ""
    problems = []
    # 守卫脚本 appendChild 后 DOM 里的真实形态（源码里不会以此形式出现）
    if not re.search(r'<div class="fail-bar fail-error" role="alert">', dom):
        problems.append("未渲染出启动错误条（role=alert）")
    if not re.search(r'报告未能完成初始化', dom):
        problems.append("错误条缺少说明文案")
    if not re.search(r'<button type="button" class="fail-act">重新加载</button>', dom):
        problems.append("错误条缺少「重新加载」按钮")
    print("%s %-32s DOM %8d 字符" % ("ok  " if not problems else "FAIL", "启动守卫（语法错误兜底）", len(dom)))
    for p in problems:
        print("       - %s" % p)
    return 1 if problems else 0


def dump(hash_, budget=9000, attempts=3):
    """跑一次 Chrome --dump-dom 拿渲染后的 DOM。

    实测 Chrome（headless=new）偶发返回 0 字符（临时 profile 竞态 / 启动抖动），
    与页面本身无关。原先直接判失败，表现为「同一个场景第一次挂、重跑就过」的假警报，
    会让真回归淹没在噪声里——所以空结果一律重试，只在连续 attempts 次都空时才作数。
    """
    url = TARGET.as_uri() + hash_
    out = ""
    for i in range(attempts):
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
            out = r.stdout or ""
        if len(out) >= 20000:
            return out
        if i + 1 < attempts:
            time.sleep(0.6)
    return out


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
        # 限定区域断言：先锚定到某个渲染元素，只在它后面的 size 字符内匹配。
        # 这是唯一能在「源码内联进同一个 DOM」的前提下区分「渲染出来」与「源码里写着」的办法。
        # 这是唯一能在「源码内联进同一个 DOM」的前提下区分「渲染出来」与「源码里写着」的办法。
        for sc in case.get("scoped", []):
            m = re.search(sc["anchor"], dom)
            if not m:
                problems.append("区域 %s：找不到锚点 /%s/" % (sc["label"], sc["anchor"]))
                continue
            seg = dom[m.start():m.start() + sc.get("size", 500)]
            for pat in sc.get("yes", []):
                if not re.search(pat, seg):
                    problems.append("区域 %s：未命中 /%s/" % (sc["label"], pat))
            for pat in sc.get("no", []):
                if re.search(pat, seg):
                    problems.append("区域 %s：不应命中 /%s/" % (sc["label"], pat))
        m = re.search(r'<button data-view="(?P<v>[a-z]+)"[^>]*aria-selected="true"', dom)
        print("%s %-32s DOM %8d 字符  tab=%s" % (
            "ok  " if not problems else "FAIL", case["name"], len(dom), m.group("v") if m else "?"))
        for p in problems:
            print("       - %s" % p)
        if problems:
            failures.append(case["name"])
    guard_fail = check_boot_guard()
    total = len(CASES) + 1
    failed = len(failures) + guard_fail
    print("\n" + "=" * 60)
    print("通过 %d / 失败 %d" % (total - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
