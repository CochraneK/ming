# -*- coding: utf-8 -*-
"""逐章充分性审计：书籍原文是否充分 + 抽取密度是否异常。

输出：
  1) 每章正文长度分布，标记"书籍不充分"(正文过短) 的真实章节
  2) 每章被抽取人物/事件数，标记"正文够长但抽取密度异常低"(疑似漏抽) 的章节
  3) 整体结论：是否还有可继续抽取的空间
"""
import os, json, re, statistics

BASE = os.environ.get("BASE") or "D:/2026/WB项目/明朝"
chaps = json.load(open(BASE + "/data/chapters.json", encoding="utf-8"))
data = json.load(open(BASE + "/data/data.json", encoding="utf-8"))

# 章节正文映射
body = {}
for ch in chaps:
    k = ch.get("key")
    body[k] = ch.get("body", "") or ""

# 真实内容章节(正文>200字, 排除 frontmatter/分卷分隔)
real = {k: b for k, b in body.items() if len(b) > 200}
print("总条目=%d | 正文空条目=%d | 真实内容章节=%d" %
      (len(body), sum(1 for b in body.values() if len(b) == 0), len(real)))

# 每章抽取量
char_chaps = {}
for c in data["characters"]:
    for k in (c.get("chapters") or []):
        char_chaps.setdefault(k, set()).add(c["name"])
    for k in (c.get("chapters_derived") or []):
        char_chaps.setdefault(k, set()).add(c["name"])
ev_chaps = {}
for e in (data.get("events") or []):
    for k in (e.get("chapters") or []):
        ev_chaps.setdefault(k, 0)
        ev_chaps[k] += 1

lens = sorted(len(b) for b in real.values())
print("真实章节正文长度 min/median/mean/max = %d / %d / %d / %d" %
      (lens[0], lens[len(lens)//2], round(statistics.mean(lens)), lens[-1]))

# ---- 维度1：书籍不充分(正文过短) ----
THIN = 3000  # 低于此视为"书籍内容偏薄"
thin = sorted(((k, len(b)) for k, b in real.items() if len(b) < THIN),
              key=lambda x: x[1])
print("\n=== [书籍不充分] 正文 < %d 字的真实章节(%d 章) ===" % (THIN, len(thin)))
for k, l in thin:
    print("  %-10s %6d 字 | 人物=%d 事件=%d" %
          (k, l, len(char_chaps.get(k, ())), ev_chaps.get(k, 0)))

# ---- 维度2：正文够长但抽取密度异常低(疑似漏抽) ----
dens = []
for k, b in real.items():
    n = len(char_chaps.get(k, ())) + ev_chaps.get(k, 0)
    d = n * 10000.0 / len(b)
    dens.append((k, len(b), n, d))
dens.sort(key=lambda x: x[3])
med_len = lens[len(lens)//2]
cut = max(1, int(len(dens) * 0.05))
low = [r for r in dens[:cut] if r[1] >= med_len * 0.6]
print("\n=== [疑似漏抽] 正文>=中位60%% 但密度最低5%% 的章节 ===")
print("(全体密度 median=%.2f 每万字)" % (statistics.median(r[3] for r in dens)))
for k, l, n, d in low:
    print("  %-10s 正文=%6d 字 | 人物+事件=%d | 密度=%.2f/万字" % (k, l, n, d))

# ---- 维度3：正文疑似截断(结尾无句末标点且偏短) ----
TERMS = "\u3002\uff01\uff1f\u2026\u201d"  # 。！？…”
trunc = [k for k, b in real.items() if len(b) < 6000 and b and b[-1] not in TERMS]
print("\n=== [疑似截断] 正文<6000且结尾无句末标点的章节(%d) ===" % len(trunc))
for k in trunc[:20]:
    print("  %-10s 末3字=[%s]" % (k, body[k][-3:]))

# ---- 引用完整性：data 里引用的章节键是否都在 chapters.json ----
ref_keys = set(char_chaps) | set(ev_chaps)
missing = sorted(k for k in ref_keys if k not in body)
print("\n=== 引用完整性 ===")
print("data 引用章节键数=%d | 在 chapters.json 缺失=%d %s" %
      (len(ref_keys), len(missing), missing[:10] if missing else "（无）"))

print("\n=== 结论速览 ===")
print("书籍不充分(薄章)数=%d | 疑似漏抽章数=%d | 疑似截断章数=%d" %
      (len(thin), len(low), len(trunc)))
