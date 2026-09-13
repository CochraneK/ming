# -*- coding: utf-8 -*-
"""① 取回线上独有的工程文件（.gitignore / requirements.txt）
② 从 main 移除误入库的 data/chapters.json（版权硬约束）
③ 统计该文件在历史里出现过的提交数（供决定是否重写历史）

走 Git Database API：建新 tree（该 path 置 sha=null 表示删除）→ 新 commit → PATCH refs。
只读+单文件删除，不动其它文件；本地那份 chapters.json 完全不受影响。
"""
import os, json, base64, subprocess, tempfile, sys

OWNER, REPO = "CochraneK", "ming"
API = f"/repos/{OWNER}/{REPO}"
BASE = r"D:\2026\WB项目\明朝"
TARGET = "data/chapters.json"

ENV = {k: v for k, v in os.environ.items()
       if k.upper() not in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")}


def gh(method, path, payload=None):
    cmd = ["gh", "api", "--method", method, path]
    tmp = None
    if payload is not None:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(payload, tmp, ensure_ascii=False)
        tmp.close()
        cmd += ["--input", tmp.name]
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV)
    if tmp:
        try: os.unlink(tmp.name)
        except Exception: pass
    if r.returncode != 0:
        raise RuntimeError(f"{method} {path} 失败:\n{r.stderr}\n{r.stdout}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


# ① 取回线上独有的工程文件
for name in (".gitignore", "requirements.txt"):
    j = gh("GET", f"{API}/contents/{name}")
    raw = base64.b64decode(j["content"])
    local = os.path.join(BASE, name)
    if os.path.exists(local):
        print(f"本地已存在 {name}，跳过")
        continue
    with open(local, "wb") as fh:
        fh.write(raw)
    print(f"已取回 {name}（{len(raw)} B）")

# ③ 历史统计（先查，便于决定是否重写历史）
hist = gh("GET", f"{API}/commits?path={TARGET}&per_page=100")
print(f"\n历史：{TARGET} 出现在 {len(hist)} 个提交中")
for c in hist[:5]:
    print("   ", c["sha"][:8], c["commit"]["author"]["date"], (c["commit"]["message"] or "")[:50].replace("\n", " "))

# ② 删除文件
ref = gh("GET", f"{API}/git/refs/heads/main")
head = ref["object"]["sha"]
base_tree = gh("GET", f"{API}/git/commits/{head}")["tree"]["sha"]
assert TARGET in [e["path"] for e in gh("GET", f"{API}/git/trees/{base_tree}?recursive=1")["tree"]], "目标不在树中"

new_tree = gh("POST", f"{API}/git/trees", {
    "base_tree": base_tree,
    "tree": [{"path": TARGET, "mode": "100644", "type": "blob", "sha": None}],   # sha=null → 删除
})["sha"]
commit = gh("POST", f"{API}/git/commits", {
    "message": "Remove: data/chapters.json（含全书正文，按版权硬约束不入公开仓库）",
    "tree": new_tree,
    "parents": [head],
})["sha"]
gh("PATCH", f"{API}/git/refs/heads/main", {"sha": commit})
print(f"\n✓ main -> {commit}")

# 验证
try:
    gh("GET", f"{API}/contents/{TARGET}")
    print("✗ 验证失败：文件仍在 main 上")
    sys.exit(1)
except Exception as e:
    print("✓ 验证通过：main 上已无", TARGET)
    print("  （注意：历史提交中仍可访问该 blob，需要重写历史才能彻底清除）")
