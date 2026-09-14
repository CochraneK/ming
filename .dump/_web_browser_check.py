# -*- coding: utf-8 -*-
"""V8 在线 boot / search / domain chunks / 人物详情二级按需的真实 Chrome 冒烟。"""
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


def assert_no_chunk(dom: str, *names: str):
    for name in names:
        if 'data-ming-data-chunk="%s"' % name in dom:
            raise AssertionError("不应加载领域块：%s" % name)


def check_home_stays_boot_only():
    dom = chrome_dump(TARGET)
    assert_has(
        dom,
        r'<html[^>]*data-ming-data="boot"',
        r'data-ming-chunks=""',
        r'data-ming-search="idle"',
        r'<button type="button" class="command-trigger"',
        r'<section class="v3-story panel"',
        r'地点已定位',
        r'事件可纪年',
    )
    if 'data-ming-data-chunk=' in dom or 'data-ming-search-chunk="index"' in dom:
        raise AssertionError("普通首页意外加载了按需数据 chunk")
    print("ok   V8 首页仅 boot，search/domain/details 均未加载")


def _command_probe(click_result: bool) -> Path:
    doc = TARGET.read_text(encoding="utf-8")
    click_js = """
  setTimeout(function(){
    var bs=[].slice.call(document.querySelectorAll('[data-command-index]'));
    var b=bs.find(function(x){return x.textContent.indexOf('于谦')>=0;});
    if(b)b.click();
  },700);
""" if click_result else ""
    probe = """<script>
setTimeout(function(){
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true}));
  var i=document.getElementById('commandInput');
  if(i){i.value='于谦';i.dispatchEvent(new Event('input',{bubbles:true}));}
%s
},120);
</script>\n""" % click_js
    probe_path = TARGET.parent / (".v8-command-click-probe.html" if click_result else ".v8-command-probe.html")
    probe_path.write_text(doc.replace("</body>", probe + "</body>", 1), encoding="utf-8")
    return probe_path


def check_command_palette_loads_search_only():
    probe_path = _command_probe(False)
    try:
        dom = chrome_dump(probe_path, budget=9000)
    finally:
        probe_path.unlink(missing_ok=True)
    assert_has(
        dom,
        r'<html[^>]*data-ming-data="boot"',
        r'data-ming-chunks=""',
        r'data-ming-search="ready"',
        r'data-ming-search-chunk="index"',
        r'<div id="commandPalette" class="command-shell">',
        r'<strong>于谦</strong>',
    )
    if 'data-ming-data-chunk=' in dom:
        raise AssertionError("仅搜索于谦时不应加载任何领域数据块")
    print("ok   V8 Ctrl+K → search-index → 于谦，DATA 仍保持 boot")


def check_character_view_loads_cards_without_details():
    dom = chrome_dump(TARGET, "#view=characters", 9500)
    assert_has(
        dom,
        r'<html[^>]*data-ming-data="partial"',
        r'data-ming-chunks="characters"',
        r'data-ming-data-chunk="characters"',
        r'id="characters" class="view active"',
        r'<article class="character-card',
        r'data-char-detail=',
    )
    assert_no_chunk(dom, "character-details", "events", "space", "relations", "time", "graphs", "insight", "meta")
    print("ok   V8 人物索引 → 仅轻量 characters 卡片层，不拉详情")


def check_command_entity_selection_loads_person_detail_domains_only():
    probe_path = _command_probe(True)
    try:
        dom = chrome_dump(probe_path, budget=11000)
    finally:
        probe_path.unlink(missing_ok=True)
    assert_has(
        dom,
        r'<html[^>]*data-ming-data="partial"',
        r'data-ming-chunks="characters,character-details,events,insight"',
        r'data-ming-search="ready"',
        r'data-ming-data-chunk="characters"',
        r'data-ming-data-chunk="character-details"',
        r'data-ming-data-chunk="events"',
        r'data-ming-data-chunk="insight"',
        r'data-ming-character-details="\d+"',
        r'id="characters" class="view active"',
        r'于谦',
        r'涉及事件',
        r'关系',
    )
    assert_no_chunk(dom, "space", "relations", "time", "graphs", "meta")
    print("ok   V8 选择人物结果 → 卡片+详情补丁+events+insight，不拉全库")


def check_chronicle_loads_time_and_cards_without_details():
    dom = chrome_dump(TARGET, "#view=chronicle", 9500)
    assert_has(
        dom,
        r'<html[^>]*data-ming-data="partial"',
        r'data-ming-chunks="characters,time"',
        r'data-ming-data-chunk="characters"',
        r'data-ming-data-chunk="time"',
        r'id="chronicle" class="view active"',
        r'年谱 · 人物生平对照',
        r'data-person=',
    )
    assert_no_chunk(dom, "character-details", "events", "space", "relations", "graphs", "insight", "meta")
    print("ok   V8 年谱 deep link → time+轻量 characters，不拉人物详情")


def check_visual_deep_link_loads_graph_only_before_app():
    dom = chrome_dump(TARGET, "#view=visuals&net=full", 9500)
    assert_has(
        dom,
        r'<html[^>]*data-ming-data="partial"',
        r'data-ming-chunks="graphs"',
        r'data-ming-data-chunk="graphs"',
        r'id="visuals" class="view active"',
        r'<div class="v3-graph-reader" data-mode="full"[^>]*>',
        r'人物总图怎么读',
        r'data-v3-node-search',
    )
    assert_no_chunk(dom, "characters", "character-details", "events", "space", "relations", "time", "insight", "meta")
    print("ok   V8 图谱 deep link → 仅 graphs")


def check_timeline_deep_link_loads_time_and_events_only():
    dom = chrome_dump(TARGET, "#view=timeline&from=1449&to=1457", 9500)
    assert_has(
        dom,
        r'<html[^>]*data-ming-data="partial"',
        r'data-ming-chunks="events,time"',
        r'data-ming-data-chunk="events"',
        r'data-ming-data-chunk="time"',
        r'id="timeline" class="view active"',
        r'1449',
        r'1457',
    )
    assert_no_chunk(dom, "characters", "character-details", "space", "relations", "graphs", "insight", "meta")
    print("ok   V8 时间轴 deep link → 仅 events+time")


if __name__ == "__main__":
    if not TARGET.exists():
        raise SystemExit("目标文件不存在：%s" % TARGET)
    check_home_stays_boot_only()
    check_command_palette_loads_search_only()
    check_character_view_loads_cards_without_details()
    check_command_entity_selection_loads_person_detail_domains_only()
    check_chronicle_loads_time_and_cards_without_details()
    check_visual_deep_link_loads_graph_only_before_app()
    check_timeline_deep_link_loads_time_and_events_only()
