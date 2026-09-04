# -*- coding: utf-8 -*-
# 部署当前本地 index.html 到 CochraneK/ming 根目录（main 分支），
# 走 Git Database API（4MB 超 Contents API 1MB 限制）。
# 仅更新 index.html，base_tree 保留其余文件。沙箱 gh 需清代理。
import os, json, base64, subprocess, tempfile

OWNER = "CochraneK"
REPO  = "ming"
LOCAL = "D:/2026/WB项目/明朝/index.html"
SW    = "D:/2026/WB项目/明朝/sw.js"
README_MD = "D:/2026/WB项目/明朝/README.md"
API   = f"/repos/{OWNER}/{REPO}"

ENV = {k: v for k, v in os.environ.items()}
for k in list(ENV):
    if k.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY") or k.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        del ENV[k]

def gh(method, path, input_obj=None):
    cmd = ["gh", "api", "--method", method, path]
    tmp = None
    if input_obj is not None:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(input_obj, tmp, ensure_ascii=False)
        tmp.close()
        cmd += ["--input", tmp.name]
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV)
    if tmp:
        try: os.unlink(tmp.name)
        except: pass
    if r.returncode != 0:
        raise RuntimeError(f"gh {method} {path} failed:\n{r.stderr}\n{r.stdout}")
    return json.loads(r.stdout) if r.stdout.strip() else {}

# 1) blob (index.html)
with open(LOCAL, "rb") as fh:
    b64 = base64.b64encode(fh.read()).decode("ascii")
print(f"local index.html: {os.path.getsize(LOCAL)//1024} KB")
blob_sha = gh("POST", f"{API}/git/blobs", {"content": b64, "encoding": "base64"})["sha"]
print("blob(index):", blob_sha)

# 1b) blob (sw.js)
with open(SW, "rb") as fh:
    sw_b64 = base64.b64encode(fh.read()).decode("ascii")
print(f"local sw.js: {os.path.getsize(SW)} B")
sw_sha = gh("POST", f"{API}/git/blobs", {"content": sw_b64, "encoding": "base64"})["sha"]
print("blob(sw):", sw_sha)

# 1c) blob (README.md)
with open(README_MD, "rb") as fh:
    rd_b64 = base64.b64encode(fh.read()).decode("ascii")
print(f"local README.md: {os.path.getsize(README_MD)} B")
rd_sha = gh("POST", f"{API}/git/blobs", {"content": rd_b64, "encoding": "base64"})["sha"]
print("blob(readme):", rd_sha)

# 2) base tree
ref = gh("GET", f"{API}/git/refs/heads/main")
head_sha = ref["object"]["sha"]
base_tree = gh("GET", f"{API}/git/commits/{head_sha}")["tree"]["sha"]
print("HEAD:", head_sha, " base_tree:", base_tree)

# 3) tree (index.html + sw.js + README.md changed; rest inherited from base_tree)
tree_sha = gh("POST", f"{API}/git/trees", {
    "base_tree": base_tree,
    "tree": [
        {"path": "index.html", "mode": "100644", "type": "blob", "sha": blob_sha},
        {"path": "sw.js", "mode": "100644", "type": "blob", "sha": sw_sha},
        {"path": "README.md", "mode": "100644", "type": "blob", "sha": rd_sha},
    ],
})["sha"]

# 4) commit
commit_sha = gh("POST", f"{API}/git/commits", {
    "message": "Deploy: 学科更名 XX学 + 17 学科洞察 + 人物卡语录替代关系 + README 同步",
    "tree": tree_sha,
    "parents": [head_sha],
})["sha"]
print("commit:", commit_sha)

# 5) point main
gh("PATCH", f"{API}/git/refs/heads/main", {"sha": commit_sha})
print("✓ main ->", commit_sha)

# 6) verify
ver = gh("GET", f"{API}/contents/index.html")
print("verified remote index.html size:", ver["size"], "sha:", ver["sha"])
ver_sw = gh("GET", f"{API}/contents/sw.js")
print("verified remote sw.js size:", ver_sw["size"], "sha:", ver_sw["sha"])
ver_rd = gh("GET", f"{API}/contents/README.md")
print("verified remote README.md size:", ver_rd["size"], "sha:", ver_rd["sha"])
print("PAGES_URL=https://cochranek.github.io/ming/")
