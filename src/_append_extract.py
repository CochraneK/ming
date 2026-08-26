# -*- coding: utf-8 -*-
# 把一条/一批抽取记录安全追加进 data/extract_raw.json（按 key 去重，已存在则覆盖）。
# 用法: python src/_append_extract.py /tmp/rec.json
import json, sys, os, tempfile
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "data", "extract_raw.json")
if len(sys.argv) != 2:
    raise SystemExit("用法：python src/_append_extract.py <record.json>")
with open(sys.argv[1], encoding="utf-8") as f:
    rec = json.load(f)
recs = [rec] if isinstance(rec, dict) else rec
if not isinstance(recs, list):
    raise SystemExit("输入必须是 JSON 对象或对象数组")
with open(RAW, encoding="utf-8") as f:
    raw = json.load(f)
existing = {e["key"] for e in raw}
added = 0
for e in recs:
    if e["key"] in existing:
        for i, x in enumerate(raw):
            if x["key"] == e["key"]:
                raw[i] = e
                break
    else:
        raw.append(e)
        existing.add(e["key"])
        added += 1
fd, temp_path = tempfile.mkstemp(prefix=".extract-", dir=os.path.dirname(RAW), text=True)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temp_path, RAW)
except Exception:
    if os.path.exists(temp_path):
        os.remove(temp_path)
    raise
print(f"新增 {added}，现有总计 {len(raw)} 条")
