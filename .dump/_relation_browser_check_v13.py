# -*- coding: utf-8 -*-
"""V13 关系索引真实 Chrome 冒烟：关系页只加载 relation core，不预取 metadata。"""
from __future__ import annotations
import os,re,shutil,subprocess,sys,tempfile
from pathlib import Path

TARGET=(Path(sys.argv[1]) if len(sys.argv)>1 else Path('dist/full/index.html')).resolve()


def find_chrome():
    env=os.environ.get('CHROME_BIN')
    if env and Path(env).exists():return env
    for name in ('google-chrome','chrome','chromium','chromium-browser'):
        found=shutil.which(name)
        if found:return found
    for cand in ('/usr/bin/google-chrome','/usr/bin/chromium'):
        if Path(cand).exists():return cand
    return None


def chrome_dump(hash_:str,budget:int=10000)->str:
    chrome=find_chrome()
    if not chrome:raise SystemExit('未找到 Chrome / Chromium')
    with tempfile.TemporaryDirectory() as prof:
        cmd=[chrome,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-extensions','--allow-file-access-from-files','--user-data-dir='+prof,'--virtual-time-budget=%d'%budget,'--dump-dom',TARGET.as_uri()+hash_]
        if hasattr(os,'geteuid') and os.geteuid()==0:cmd.insert(1,'--no-sandbox')
        r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace')
        if not r.stdout:raise AssertionError('Chrome 未返回 DOM：%s'%((r.stderr or '').strip()[-500:]))
        return r.stdout


def check_relation_core_only():
    dom=chrome_dump('#view=relations')
    for pattern in (r'data-ming-chunks="relations"',r'data-ming-data-chunk="relations"',r'id="relations" class="view active"',r'关系索引',r'<table class="data-table">'):
        if not re.search(pattern,dom,re.S):raise AssertionError('缺少关系页渲染结果：%s'%pattern)
    if 'data-ming-data-chunk="relation-meta"' in dom:
        raise AssertionError('关系索引不应预取 relation-meta')
    print('ok   V13 关系索引仅 relation core，不预取 metadata')


if __name__=='__main__':
    if not TARGET.exists():raise SystemExit('目标文件不存在：%s'%TARGET)
    check_relation_core_only()
