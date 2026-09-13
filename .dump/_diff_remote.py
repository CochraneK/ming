# -*- coding: utf-8 -*-
"""本地 ↔ GitHub 全量差异比对（blob sha 口径）。

只读，不改动任何文件。用于回答「哪些没传 / 哪些过时」。
- 本地 git blob sha：sha1(b'blob %d\\0' % len + bytes)，与 GitHub tree 同口径。
- 有意排除：明朝那些事儿.txt、data/chapters.json（版权）、缓存/临时产物。
"""
import os, sys, json, hashlib, subprocess

BASE = r"D:\2026\WB项目\明朝"
API = "/repos/CochraneK/ming"

EXCLUDE_DIRS = {".git", "__pycache__", "_archive", "outputs", "dist", "git-sync"}
EXCLUDE_NAMES = {"明朝那些事儿.txt", "chapters.json"}
EXCLUDE_SUFFIX = (".pyc", ".tmp", ".log", ".html.tmp", "_out.txt")


def local_sha(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def walk():
    out = {}
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for name in files:
            if name in EXCLUDE_NAMES or name.endswith(EXCLUDE_SUFFIX):
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, BASE).replace(os.sep, "/")
            out[rel] = local_sha(full)
    return out


def main():
    env = {k: v for k, v in os.environ.items()
           if k.upper() not in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")}
    r = subprocess.run(["gh", "api", f"{API}/git/trees/main?recursive=1"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print("拉取线上 tree 失败:", r.stderr)
        sys.exit(1)
    remote = {e["path"]: e["sha"] for e in json.loads(r.stdout)["tree"] if e.get("type") == "blob"}
    local = walk()

    missing = sorted(set(local) - set(remote))            # 本地有、线上无
    stale = sorted(p for p in set(local) & set(remote) if local[p] != remote[p])  # 两边不同
    only_remote = sorted(set(remote) - set(local))        # 线上有、本地无

    print(f"本地 {len(local)} 个文件 / 线上 {len(remote)} 个")
    print(f"\n[未传] 本地有、线上无：{len(missing)}")
    for p in missing:
        print("   -", p)
    print(f"\n[过时] 两边都有但内容不同：{len(stale)}")
    for p in stale:
        print("   -", p)
    print(f"\n[仅线上] 线上有、本地无：{len(only_remote)}")
    for p in only_remote[:40]:
        print("   -", p)
    print("\n结论：", "完全一致 ✅" if not (missing or stale) else "存在差异，见上 ⬆")


if __name__ == "__main__":
    main()
