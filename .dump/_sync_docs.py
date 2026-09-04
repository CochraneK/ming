# -*- coding: utf-8 -*-
# 同步文档到 GitHub：README（根目录）+ .workbuddy/（memory 全部 + skill）。
# 走 Git Database API（blob→tree→commit→PATCH refs），base_tree 继承其余文件。
import os, json, base64, subprocess, tempfile

OWNER = "CochraneK"
REPO  = "ming"
API   = f"/repos/{OWNER}/{REPO}"
BASE  = "D:/2026/WB项目/明朝"

# (本地路径, 仓库路径)
# 全量同步清单（源码+数据+文档）。**有意排除**：明朝那些事儿.txt、data/chapters.json（版权）
FILES = [
    ("README.md", "README.md"),
    ("index.html", "index.html"),
    ("sw.js", "sw.js"),
    # 源码
    ("src/generate_report.py", "src/generate_report.py"),
    ("src/insight_content.py", "src/insight_content.py"),
    ("src/merge.py", "src/merge.py"),
    ("src/enrich_geo.py", "src/enrich_geo.py"),
    ("src/enrich_relations.py", "src/enrich_relations.py"),
    ("src/derive_coverage.py", "src/derive_coverage.py"),
    ("src/discover_persons.py", "src/discover_persons.py"),
    ("src/audit_final.py", "src/audit_final.py"),
    ("src/audit_chapter_sufficiency.py", "src/audit_chapter_sufficiency.py"),
    ("src/dump_chapters.py", "src/dump_chapters.py"),
    ("src/split_chapters.py", "src/split_chapters.py"),
    ("src/extract_auto.py", "src/extract_auto.py"),
    ("src/clean_rules.py", "src/clean_rules.py"),
    ("src/append_batch.py", "src/append_batch.py"),
    ("src/_append_extract.py", "src/_append_extract.py"),
    ("src/_dump_chapter.py", "src/_dump_chapter.py"),
    # 数据（增量层 + 成品）
    ("data/data.json", "data/data.json"),
    ("data/extract_raw.json", "data/extract_raw.json"),
    ("data/character_quotes.json", "data/character_quotes.json"),
    ("data/event_places.json", "data/event_places.json"),
    ("data/reigns.json", "data/reigns.json"),
    ("data/geo_annotations.json", "data/geo_annotations.json"),
    ("data/derived_chapter_persons.json", "data/derived_chapter_persons.json"),
    ("data/lifespans.json", "data/lifespans.json"),
    ("data/char_profiles.json", "data/char_profiles.json"),
    ("data/manual_corrections.json", "data/manual_corrections.json"),
    ("data/manual_event_years.json", "data/manual_event_years.json"),
    ("data/manual_lifespans.json", "data/manual_lifespans.json"),
    ("data/manual_persons.json", "data/manual_persons.json"),
    ("data/manual_relations.json", "data/manual_relations.json"),
    ("data/voyages.json", "data/voyages.json"),
    # 部署/同步脚本
    (".dump/_deploy_index_now.py", ".dump/_deploy_index_now.py"),
    (".dump/_sync_docs.py", ".dump/_sync_docs.py"),
    # 文档
    (".workbuddy/skills/ming-report-engineering/SKILL.md", ".workbuddy/skills/ming-report-engineering/SKILL.md"),
    (".workbuddy/memory/MEMORY.md", ".workbuddy/memory/MEMORY.md"),
    (".workbuddy/memory/2026-08-14.md", ".workbuddy/memory/2026-08-14.md"),
    (".workbuddy/memory/2026-08-18.md", ".workbuddy/memory/2026-08-18.md"),
    (".workbuddy/memory/2026-08-26.md", ".workbuddy/memory/2026-08-26.md"),
    (".workbuddy/memory/2026-08-28.md", ".workbuddy/memory/2026-08-28.md"),
    (".workbuddy/memory/2026-08-29.md", ".workbuddy/memory/2026-08-29.md"),
    (".workbuddy/memory/2026-08-31.md", ".workbuddy/memory/2026-08-31.md"),
    (".workbuddy/memory/2026-09-03.md", ".workbuddy/memory/2026-09-03.md"),
    (".workbuddy/memory/2026-09-04.md", ".workbuddy/memory/2026-09-04.md"),
]

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

# 1) blobs
tree_entries = []
for local, remote in FILES:
    full = os.path.join(BASE, local)
    with open(full, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    sha = gh("POST", f"{API}/git/blobs", {"content": b64, "encoding": "base64"})["sha"]
    tree_entries.append({"path": remote, "mode": "100644", "type": "blob", "sha": sha})
    print(f"blob: {remote} ({os.path.getsize(full)} B)")

# 2) base tree
ref = gh("GET", f"{API}/git/refs/heads/main")
head_sha = ref["object"]["sha"]
base_tree = gh("GET", f"{API}/git/commits/{head_sha}")["tree"]["sha"]
print("HEAD:", head_sha, " base_tree:", base_tree)

# 3) tree（其余文件继承）
tree_sha = gh("POST", f"{API}/git/trees", {"base_tree": base_tree, "tree": tree_entries})["sha"]

# 4) commit + 指针
commit_sha = gh("POST", f"{API}/git/commits", {
    "message": "Docs sync: engineering skill + workbuddy memory logs + readme",
    "tree": tree_sha,
    "parents": [head_sha],
})["sha"]
gh("PATCH", f"{API}/git/refs/heads/main", {"sha": commit_sha})
print("commit:", commit_sha)
print("✓ main ->", commit_sha)

# 5) 抽验
ver = gh("GET", f"{API}/contents/.workbuddy/skills/ming-report-engineering/SKILL.md")
print("verified SKILL.md size:", ver["size"], "sha:", ver["sha"])
ver2 = gh("GET", f"{API}/contents/.workbuddy/memory/MEMORY.md")
print("verified MEMORY.md size:", ver2["size"], "sha:", ver2["sha"])
