# -*- coding: utf-8 -*-
"""Classic UI + V13 现代在线交付的真实 Chrome 回归。

复用 V12 在线分层套件中与可见体验层无关的场景，只替换四条曾依赖
V3 command palette / graph reader 的断言：
- 首页：保持 boot，且不出现 V2/V3 可见覆盖层；
- search-index：直接调用底层 loader API，证明后端能力保留但不暴露旧命令面板；
- 人物详情：使用原生 deep link，而不是命令面板结果点击；
- 图谱：验证原始 full graph DOM，而不是 V3 reader。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import _web_browser_check as base

TARGET = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/full/index.html")).resolve()
base.TARGET = TARGET


def check_home():
    dom = base.chrome_dump(TARGET)
    base.assert_has(
        dom,
        r'<html[^>]*data-ming-data="boot"',
        r'data-ming-chunks=""',
        r'data-ming-search="idle"',
        r'<nav class="tabs"',
        r'<button data-view="overview"[^>]*>总览</button>',
    )
    for forbidden in (r'class="command-trigger"', r'class="v3-story panel"', r'class="nav-cluster"'):
        if re.search(forbidden, dom, re.S):
            raise AssertionError("Classic UI 首页不应出现：%s" % forbidden)
    if 'data-ming-data-chunk=' in dom or 'data-ming-search-chunk="index"' in dom:
        raise AssertionError("首页意外加载按需块")
    print("ok   Classic UI 在线首页仅 boot")


def _search_loader_probe():
    doc = TARGET.read_text(encoding="utf-8")
    probe = """<script>
setTimeout(function(){
  if(typeof window.__MING_ENSURE_SEARCH_INDEX!=='function'){
    document.documentElement.dataset.classicSearchProbe='missing';return;
  }
  window.__MING_ENSURE_SEARCH_INDEX('classic-test').then(function(){
    document.documentElement.dataset.classicSearchProbe='ready';
  }).catch(function(){document.documentElement.dataset.classicSearchProbe='error';});
},120);
</script>\n"""
    p = TARGET.parent / ".classic-search-probe.html"
    p.write_text(doc.replace("</body>", probe + "</body>", 1), encoding="utf-8")
    return p


def check_search_backend_only():
    p = _search_loader_probe()
    try:
        dom = base.chrome_dump(p, budget=9000)
    finally:
        p.unlink(missing_ok=True)
    base.assert_has(
        dom,
        r'data-classic-search-probe="ready"',
        r'data-ming-data="boot"',
        r'data-ming-search="ready"',
        r'data-ming-search-chunk="index"',
    )
    if 'data-ming-data-chunk=' in dom:
        raise AssertionError("只测试 search-index 时不应加载领域块")
    if re.search(r'id="commandPalette"|class="command-shell"', dom, re.S):
        raise AssertionError("Classic UI 不应恢复可见命令面板")
    print("ok   Classic UI 保留 lazy search-index 后端，不暴露命令面板")


def check_person_detail_deep_link():
    dom = base.chrome_dump(
        TARGET,
        "#view=characters&person=%E4%BA%8E%E8%B0%A6&detail=1",
        11000,
    )
    base.assert_has(
        dom,
        r'data-ming-chunks="characters,character-detail-13,insight"',
        r'data-ming-data-chunk="character-detail-13"',
        r'data-ming-data-chunk="insight"',
        r'id="characters" class="view active"',
        r'<dialog id="detailDialog" open',
        r'于谦',
        r'关系',
    )
    base.assert_only_shard(dom, base.CHAR_SHARDS, 'character-detail-13', '人物')
    base.assert_no_chunk(
        dom,
        'events', *base.EVENT_SHARDS, 'locations', *base.LOC_SHARDS,
        'place-chapters', 'voyages', 'relations', 'time', 'lifespans', 'graphs', 'meta',
    )
    print("ok   Classic UI 于谦 deep link 只取人物目标 shard + insight")


def check_graph_classic():
    dom = base.chrome_dump(TARGET, "#view=visuals&net=full", 9500)
    base.assert_has(
        dom,
        r'data-ming-chunks="graphs"',
        r'data-ming-data-chunk="graphs"',
        r'id="visuals" class="view active"',
        r'id="fullNet" style="display:block"',
        r'<canvas id="fullGraph"[^>]*role="img"',
        r'aria-label="全书人物关系图：\d+ 人、\d+ 条人物关系',
    )
    if re.search(r'data-v3-node-search|class="v3-graph-reader"', dom, re.S):
        raise AssertionError("Classic UI 图谱不应出现 V3 reader")
    base.assert_no_chunk(
        dom,
        'characters', *base.CHAR_SHARDS, 'locations', *base.LOC_SHARDS,
        'events', *base.EVENT_SHARDS, 'time', 'lifespans', 'insight', 'meta',
    )
    print("ok   Classic UI 原图谱仅 graphs，无 V3 reader")


if __name__ == "__main__":
    if not TARGET.exists():
        raise SystemExit("目标文件不存在：%s" % TARGET)

    check_home()
    check_search_backend_only()
    base.check_character_index()
    check_person_detail_deep_link()
    base.check_location_index()
    base.check_place_detail()
    base.check_map_core_only()
    base.check_location_chapter_mode()
    base.check_voyage_mode()
    base.check_chronicle()
    check_graph_classic()
    base.check_timeline()
    base.check_dynasty()
    base.check_event_index_core_only()
    base.check_event_deep_link_one_shard()
