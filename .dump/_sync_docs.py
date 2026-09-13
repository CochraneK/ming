# -*- coding: utf-8 -*-
# 同步文档到 GitHub：README + 源码 + 数据 + .workbuddy/（memory + skill）。
# 走 Git Database API（blob→tree→commit→PATCH refs），base_tree 继承其余文件。
# 2026-09-13 增强：① 先比 blob sha，**只上传有变化的文件**（避免每次重传 4MB index.html）；
#                ② 每个 HTTP 调用失败重试 3 次（沙箱到 api.github.com 偶发 401/TLS 超时）。
import os, json, base64, subprocess, tempfile, time, hashlib
from pathlib import Path

OWNER = "CochraneK"
REPO  = "ming"
API   = f"/repos/{OWNER}/{REPO}"
# 工程根由脚本自身位置推导，避免写死本机绝对路径（换机/换盘符都能直接跑）
BASE  = str(Path(__file__).resolve().parents[1])

# 本次同步的提交说明（每次同步前改这一行，或用环境变量覆盖）
MESSAGE = os.environ.get("MING_SYNC_MESSAGE") or "Docs sync: 源码 / 数据 / 文档"

# (本地路径, 仓库路径)
# 全量同步清单（源码+数据+文档）。**有意排除**：明朝那些事儿.txt、data/chapters.json（版权）
FILES = [
    ("README.md", "README.md"),
    ("index.html", "index.html"),
    ("sw.js", "sw.js"),
    # 源码
    ("src/generate_report.py", "src/generate_report.py"),
    # 构建入口 + 校验（Phase 4/5）
    ("src/build.py", "src/build.py"),
    ("src/validators.py", "src/validators.py"),
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
    # 共享核心（2026-09-13 新增：生产与审计共用的年份/经纬度语义）
    ("src/core/__init__.py", "src/core/__init__.py"),
    ("src/core/year_parser.py", "src/core/year_parser.py"),
    ("src/core/geo.py", "src/core/geo.py"),
    # 共享核心（2026-09-13 第二轮：势力结构化 P2-03 / 双模式图布局 Phase 6）
    ("src/core/faction_profile.py", "src/core/faction_profile.py"),
    ("src/core/graph_layout.py", "src/core/graph_layout.py"),
    # 共享核心（洞察实体联动：正向/反向索引，构建期生成）
    ("src/core/insight_link.py", "src/core/insight_link.py"),
    # 共享核心（地点「别称」与「书中提及」分级）
    ("src/core/place_mentions.py", "src/core/place_mentions.py"),
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
    (".dump/_diff_remote.py", ".dump/_diff_remote.py"),
    (".dump/_remove_book_text.py", ".dump/_remove_book_text.py"),
    # Phase 4 模板拆分工具（可复现 web/ 的由来）
    (".dump/_split_template.py", ".dump/_split_template.py"),
    (".dump/_migrate_template.py", ".dump/_migrate_template.py"),
    (".dump/_check_split.py", ".dump/_check_split.py"),
    # Phase 6 前置重构：两处重复的人物详情模板收敛为 showPerson()
    (".dump/_refactor_person_detail.py", ".dump/_refactor_person_detail.py"),
    # 无头浏览器自检（CI 里由 .github/workflows/ci.yml 调用，必须在仓库里）
    (".dump/_browser_check.py", ".dump/_browser_check.py"),
    # 前端资源（Phase 4：模板/CSS/JS 从 Python 字面量拆出，构建时内联）
    ("web/template/index.html", "web/template/index.html"),
    ("web/css/app.css", "web/css/app.css"),
    ("web/js/app.js", "web/js/app.js"),
    # 测试与 CI（Phase 5）
    ("tests/conftest.py", "tests/conftest.py"),
    ("tests/_support.py", "tests/_support.py"),
    ("tests/run_tests.py", "tests/run_tests.py"),
    ("tests/test_core.py", "tests/test_core.py"),
    ("tests/test_data_invariants.py", "tests/test_data_invariants.py"),
    ("tests/test_template.py", "tests/test_template.py"),
    (".github/workflows/ci.yml", ".github/workflows/ci.yml"),
    # 工程文件（2026-09-13 从线上取回本地）
    (".gitignore", ".gitignore"),
    ("requirements.txt", "requirements.txt"),
    # 文档
    ("report/Ming_全面重构方案.txt", "report/Ming_全面重构方案.txt"),
    ("report/Ming_重构验收清单.md", "report/Ming_重构验收清单.md"),
    ("report/Ming_自查报告_2026-09-14.md", "report/Ming_自查报告_2026-09-14.md"),
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
    (".workbuddy/memory/2026-09-13.md", ".workbuddy/memory/2026-09-13.md"),
    (".workbuddy/memory/2026-09-14.md", ".workbuddy/memory/2026-09-14.md"),
]

ENV = {k: v for k, v in os.environ.items()}
for k in list(ENV):
    if k.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY") or k.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        del ENV[k]

def gh(method, path, input_obj=None):
    last = None
    for attempt in range(3):
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
        if r.returncode == 0:
            return json.loads(r.stdout) if r.stdout.strip() else {}
        last = f"gh {method} {path} failed:\n{r.stderr}\n{r.stdout}"
        if attempt < 2:
            print(f"  重试 {attempt+1}/2（{r.stderr.strip().splitlines()[-1][:60] if r.stderr.strip() else '?'}）")
            time.sleep(2 + attempt * 3)
    raise RuntimeError(last)


def local_blob_sha(data: bytes) -> str:
    """git blob sha：与线上 tree 的 sha 同口径，用于跳过未变化文件。"""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# 1) 线上 tree（用于跳过未变化文件）
remote_sha = {}
try:
    tree = gh("GET", f"{API}/git/trees/main?recursive=1")
    remote_sha = {e["path"]: e["sha"] for e in tree.get("tree", []) if e.get("type") == "blob"}
    print(f"线上文件 {len(remote_sha)} 个，开始比对…")
except Exception as ex:
    print("拉取线上 tree 失败（将全量上传）：", ex)

# 2) blobs（只传变化的）
tree_entries = []
skipped = []
for local, remote in FILES:
    full = os.path.join(BASE, local)
    with open(full, "rb") as fh:
        raw = fh.read()
    sha = local_blob_sha(raw)
    if remote_sha.get(remote) == sha:
        tree_entries.append({"path": remote, "mode": "100644", "type": "blob", "sha": sha})
        skipped.append(remote)
        continue
    b64 = base64.b64encode(raw).decode("ascii")
    sha = gh("POST", f"{API}/git/blobs", {"content": b64, "encoding": "base64"})["sha"]
    tree_entries.append({"path": remote, "mode": "100644", "type": "blob", "sha": sha})
    print(f"blob: {remote} ({len(raw)} B)")
print(f"未变化跳过 {len(skipped)} 个 / 共 {len(FILES)} 个")

# 2) base tree
ref = gh("GET", f"{API}/git/refs/heads/main")
head_sha = ref["object"]["sha"]
base_tree = gh("GET", f"{API}/git/commits/{head_sha}")["tree"]["sha"]
print("HEAD:", head_sha, " base_tree:", base_tree)

# 3) tree（其余文件继承）
tree_sha = gh("POST", f"{API}/git/trees", {"base_tree": base_tree, "tree": tree_entries})["sha"]

# 4) commit + 指针
commit_sha = gh("POST", f"{API}/git/commits", {
    "message": MESSAGE,
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
