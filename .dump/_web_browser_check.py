# -*- coding: utf-8 -*-
"""V11 在线人物/地点分片、空间层与时间层按需的真实 Chrome 冒烟。"""
from __future__ import annotations
import os,re,shutil,subprocess,sys,tempfile
from pathlib import Path

TARGET=(Path(sys.argv[1]) if len(sys.argv)>1 else Path('dist/full/index.html')).resolve()
CHAR_SHARDS=tuple('character-detail-%02d'%i for i in range(16))
LOC_SHARDS=tuple('location-detail-%02d'%i for i in range(8))


def find_chrome():
    env=os.environ.get('CHROME_BIN')
    if env and Path(env).exists():return env
    for name in ('google-chrome','chrome','chromium','chromium-browser'):
        found=shutil.which(name)
        if found:return found
    for cand in ('/usr/bin/google-chrome','/usr/bin/chromium'):
        if Path(cand).exists():return cand
    return None


def chrome_dump(path:Path,hash_:str='',budget:int=8000)->str:
    chrome=find_chrome()
    if not chrome:raise SystemExit('未找到 Chrome / Chromium')
    with tempfile.TemporaryDirectory() as prof:
        cmd=[chrome,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-extensions','--allow-file-access-from-files','--user-data-dir='+prof,'--virtual-time-budget=%d'%budget,'--dump-dom',path.as_uri()+hash_]
        if hasattr(os,'geteuid') and os.geteuid()==0:cmd.insert(1,'--no-sandbox')
        r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace')
        if not r.stdout:raise AssertionError('Chrome 未返回 DOM：%s'%((r.stderr or '').strip()[-500:]))
        return r.stdout


def assert_has(dom,*patterns):
    for p in patterns:
        if not re.search(p,dom,re.S):raise AssertionError('缺少渲染结果：%s'%p)


def assert_no_chunk(dom,*names):
    for name in names:
        if 'data-ming-data-chunk="%s"'%name in dom:raise AssertionError('不应加载领域块：%s'%name)


def assert_only_shard(dom,names,expected,label):
    loaded=[n for n in names if 'data-ming-data-chunk="%s"'%n in dom]
    if loaded!=[expected]:raise AssertionError('%s shard 错误：expected=%s loaded=%s'%(label,expected,loaded))


def check_home():
    dom=chrome_dump(TARGET)
    assert_has(dom,r'<html[^>]*data-ming-data="boot"',r'data-ming-chunks=""',r'data-ming-search="idle"',r'class="command-trigger"',r'class="v3-story panel"')
    if 'data-ming-data-chunk=' in dom or 'data-ming-search-chunk="index"' in dom:raise AssertionError('首页意外加载按需块')
    print('ok   V11 首页仅 boot')


def _command_probe(click=False):
    doc=TARGET.read_text(encoding='utf-8')
    click_js="""setTimeout(function(){var bs=[].slice.call(document.querySelectorAll('[data-command-index]'));var b=bs.find(function(x){return x.textContent.indexOf('于谦')>=0;});if(b)b.click();},700);""" if click else ''
    probe="""<script>setTimeout(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true}));var i=document.getElementById('commandInput');if(i){i.value='于谦';i.dispatchEvent(new Event('input',{bubbles:true}));}%s},120);</script>\n"""%click_js
    p=TARGET.parent/('.v11-command-click.html' if click else '.v11-command.html');p.write_text(doc.replace('</body>',probe+'</body>',1),encoding='utf-8');return p


def check_search_only():
    p=_command_probe(False)
    try:dom=chrome_dump(p,budget=9000)
    finally:p.unlink(missing_ok=True)
    assert_has(dom,r'data-ming-data="boot"',r'data-ming-search="ready"',r'data-ming-search-chunk="index"',r'<strong>于谦</strong>')
    if 'data-ming-data-chunk=' in dom:raise AssertionError('搜索未选择结果时不应加载领域块')
    print('ok   V11 Ctrl+K 仅 search-index')


def check_character_index():
    dom=chrome_dump(TARGET,'#view=characters',9500)
    assert_has(dom,r'data-ming-chunks="characters"',r'data-ming-data-chunk="characters"',r'id="characters" class="view active"',r'class="character-card')
    assert_no_chunk(dom,*CHAR_SHARDS,*LOC_SHARDS,'locations','place-chapters','voyages','events','relations','time','lifespans','graphs','insight','meta')
    print('ok   V11 人物索引仅 cards')


def check_person_detail():
    p=_command_probe(True)
    try:dom=chrome_dump(p,budget=11000)
    finally:p.unlink(missing_ok=True)
    assert_has(dom,r'data-ming-chunks="characters,character-detail-13,events,insight"',r'data-ming-data-chunk="character-detail-13"',r'于谦',r'涉及事件',r'关系')
    assert_only_shard(dom,CHAR_SHARDS,'character-detail-13','人物')
    assert_no_chunk(dom,'locations',*LOC_SHARDS,'place-chapters','voyages','relations','time','lifespans','graphs','meta')
    print('ok   V11 于谦仅人物 shard-13')


def check_location_index():
    dom=chrome_dump(TARGET,'#view=locations',9500)
    assert_has(dom,r'data-ming-chunks="locations"',r'data-ming-data-chunk="locations"',r'id="locations" class="view active"',r'class="location-card"',r'地点索引')
    assert_no_chunk(dom,*LOC_SHARDS,'place-chapters','voyages','events','insight','relations','time','lifespans','graphs','meta')
    print('ok   V11 地点索引仅 locations 摘要')


def check_place_detail():
    dom=chrome_dump(TARGET,'#view=locations&place=%E5%AE%81%E8%BF%9C',11000)
    assert_has(dom,r'data-ming-chunks="locations,location-detail-00,events,insight"',r'data-ming-data-chunk="location-detail-00"',r'id="locations" class="view active"',r'宁远',r'书中直接关联事件',r'核验备注')
    assert_only_shard(dom,LOC_SHARDS,'location-detail-00','地点')
    assert_no_chunk(dom,'place-chapters','voyages','relations','time','lifespans','graphs','meta')
    print('ok   V11 宁远详情仅 location shard-00 + events/insight')


def check_map_core_only():
    dom=chrome_dump(TARGET,'#view=map',10000)
    assert_has(dom,r'data-ming-chunks="locations"',r'data-ming-data-chunk="locations"',r'id="map" class="view active"',r'已定位 553/583 个地点')
    assert_no_chunk(dom,*LOC_SHARDS,'place-chapters','voyages','events','insight','relations','time','lifespans','graphs','meta')
    print('ok   V11 默认地图仅 locations 摘要')


def _click_probe(selector,delay=900):
    doc=TARGET.read_text(encoding='utf-8')
    probe="<script>setTimeout(function(){var b=document.querySelector(%r);if(b)b.click();},%d);</script>\n"%(selector,delay)
    p=TARGET.parent/'.v11-click-probe.html';p.write_text(doc.replace('</body>',probe+'</body>',1),encoding='utf-8');return p


def check_location_chapter_mode():
    p=_click_probe('[data-loc-mode="chapter"]')
    try:dom=chrome_dump(p,'#view=locations',11000)
    finally:p.unlink(missing_ok=True)
    assert_has(dom,r'data-ming-chunks="locations,place-chapters"',r'data-ming-data-chunk="place-chapters"',r'class="chapter-list"')
    assert_no_chunk(dom,*LOC_SHARDS,'voyages','events','insight','time','lifespans')
    print('ok   V11 地点按章节 → 仅增量 place-chapters')


def check_chronicle():
    dom=chrome_dump(TARGET,'#view=chronicle',9500)
    assert_has(dom,r'data-ming-chunks="characters,lifespans"',r'data-ming-data-chunk="characters"',r'data-ming-data-chunk="lifespans"',r'年谱 · 人物生平对照')
    assert_no_chunk(dom,*CHAR_SHARDS,'locations',*LOC_SHARDS,'events','relations','time','graphs','insight','meta')
    print('ok   V11 年谱仅 characters+lifespans，不拉 timeline')


def check_graph():
    dom=chrome_dump(TARGET,'#view=visuals&net=full',9500)
    assert_has(dom,r'data-ming-chunks="graphs"',r'data-ming-data-chunk="graphs"',r'data-v3-node-search')
    assert_no_chunk(dom,'characters',*CHAR_SHARDS,'locations',*LOC_SHARDS,'events','time','lifespans','insight','meta')
    print('ok   V11 图谱仅 graphs')


def check_timeline():
    dom=chrome_dump(TARGET,'#view=timeline&from=1449&to=1457',9500)
    assert_has(dom,r'data-ming-chunks="events,time"',r'data-ming-data-chunk="events"',r'data-ming-data-chunk="time"',r'1449',r'1457')
    assert_no_chunk(dom,'characters',*CHAR_SHARDS,'locations',*LOC_SHARDS,'lifespans','graphs','insight','meta')
    print('ok   V11 时间轴仍仅 events+time，不拉 lifespans')


if __name__=='__main__':
    if not TARGET.exists():raise SystemExit('目标文件不存在：%s'%TARGET)
    check_home();check_search_only();check_character_index();check_person_detail()
    check_location_index();check_place_detail();check_map_core_only();check_location_chapter_mode()
    check_chronicle();check_graph();check_timeline()
