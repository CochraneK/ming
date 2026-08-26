# -*- coding: utf-8 -*-
"""把一批抽取结果(_batch.json)合并进 extract_raw.json，按 key 去重。"""
import json, os, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "data", "extract_raw.json")
BATCH = os.path.join(BASE, "data", "_batch.json")


def write_json_atomic(path, value):
    fd, temp_path = tempfile.mkstemp(prefix=".json-", dir=os.path.dirname(path), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

with open(RAW, encoding="utf-8") as f:
    raw = json.load(f)
with open(BATCH, encoding="utf-8") as f:
    batch = json.load(f)
if not isinstance(batch, list):
    batch = [batch]
existing = {e["key"] for e in raw}
added = 0
for e in batch:
    if e["key"] in existing:
        # 覆盖已有（用于修订）
        for i, x in enumerate(raw):
            if x["key"] == e["key"]:
                raw[i] = e
                break
    else:
        raw.append(e)
        existing.add(e["key"])
        added += 1
write_json_atomic(RAW, raw)
print(f"已合并：新增 {added}，现有总计 {len(raw)} 条")
