# -*- coding: utf-8 -*-
"""发布后体检：一次跑完「合规巡检 + 线上产物逐字节核对 + CI 结论」。

用法：`python .dump/_post_publish_check.py`（同步/部署之后跑）

三个必须绕开的坑：
1. **合规巡检**要查的是线上仓库的文件树（本地 `.gitignore` 挡不住 API 上传）；
2. **线上产物核对**必须绕开 GitHub Pages 的边缘缓存（`max-age=600`）；
   这里用**时间戳 cache-buster**，不能用固定查询串（会被按那个 URL 缓存住，
   实测曾拉到上一版的 sw.js 字节）；
3. `gh` 在沙箱里会继承宿主代理 `127.0.0.1:7897` 而连不通，需清掉代理环境变量。
"""
import hashlib
import io
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = "CochraneK/ming"
SITE = "https://cochranek.github.io/ming/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS = str(int(time.time()))
ENV = {k: v for k, v in os.environ.items()
       if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}

_GH = r"C:\Users\cunyi\.workbuddy\binaries\PortableGit\versions\1.2.0\bin\gh.exe"
GH = _GH if os.path.exists(_GH) else "gh"

# 必须逐字节核对的产物（其余文件由 _diff_remote.py 负责内容比对）
ARTIFACTS = [("index.html", "index.html"), ("sw.js", "sw.js")]


def _gh_api(path, jq):
    r = subprocess.run([GH, "api", path, "--jq", jq],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=ENV)
    return (r.stdout or "").strip(), (r.stderr or "").strip()


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=120) as f:
        return f.read()


def check_compliance():
    """线上的 blob 路径里绝不允许出现原书全文或章节正文。"""
    print("【1】合规巡检（线上文件树）")
    out, err = _gh_api("/repos/%s/git/trees/main?recursive=1" % REPO,
                       '.tree[]|select(.type=="blob")|.path')
    if not out:
        print("     ⚠️ 查询失败：%s" % (err or "无输出"))
        return False
    paths = [p for p in out.splitlines() if p.strip()]
    bad = [p for p in paths if re.search(r"chapters\.json|明朝那些事儿", p)]
    print("     线上 blob %d 个；敏感路径命中 %d 个 %s"
          % (len(paths), len(bad), "✅" if not bad else "⚠️ " + str(bad)))
    return not bad


def check_artifacts():
    """本地产物与线上必须逐字节一致（时间戳 cache-buster 绕 CDN）。"""
    print("\n【2】线上产物逐字节核对")
    ok = True
    for name, rel in ARTIFACTS:
        local = os.path.join(ROOT, rel)
        if not os.path.exists(local):
            print("     %-11s 本地缺失，跳过" % name)
            continue
        lb = io.open(local, "rb").read()
        try:
            rb = _fetch(SITE + name + "?ts=" + TS)
        except Exception as e:
            print("     %-11s 拉取失败：%s" % (name, e))
            ok = False
            continue
        same = hashlib.sha1(lb).digest() == hashlib.sha1(rb).digest()
        ok = ok and same
        extra = ""
        if name == "sw.js":
            m = re.search(r"CACHE_PREFIX \+ '([^']+)'", rb.decode("utf-8", "replace"))
            extra = " | CACHE=%s" % (m.group(1) if m else "?")
        print("     %-11s 本地 %d B / 线上 %d B  sha1 %s  %s%s"
              % (name, len(lb), len(rb), hashlib.sha1(lb).hexdigest()[:12],
                 "一致 ✅" if same else "不一致 ⚠️", extra))
    return ok


def check_actions(limit=6):
    print("\n【3】最近 GitHub Actions")
    out, err = _gh_api("/repos/%s/actions/runs?per_page=%d" % (REPO, limit),
                       '.workflow_runs[]|"\\(.name) | \\(.head_sha[0:8]) | \\(.status) | \\(.conclusion)"')
    if not out:
        print("     ⚠️ 查询失败：%s" % (err or "无输出"))
        return False
    ok = True
    for line in out.splitlines():
        parts = [p.strip() for p in line.split("|")]
        sha = parts[1] if len(parts) > 1 else "?"
        status = parts[2] if len(parts) > 2 else "?"
        concl = parts[3] if len(parts) > 3 else "?"
        mark = "✅" if concl == "success" else ("…" if status != "completed" else "⚠️")
        if concl not in ("success",) and status == "completed":
            ok = False
        print("     %s %s" % (mark, line))
    return ok


if __name__ == "__main__":
    a = check_compliance()
    b = check_artifacts()
    c = check_actions()
    print("\n========================================")
    print("合规 %s · 产物 %s · CI %s" % (
        "✅" if a else "⚠️", "✅" if b else "⚠️", "✅" if c else "⚠️"))
    sys.exit(0 if (a and b) else 1)
