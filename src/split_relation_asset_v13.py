# -*- coding: utf-8 -*-
"""V13 在线关系物理分层：可见关系 core + deferred metadata。

最终 DATA、generate_report 与 standalone 完全不变。该脚本只处理已构建的 web 产物：
- data-relations.js 仅保留关系索引真正渲染/筛选所需字段；
- id/sourceId/targetId/sourceType/targetType/source/endpointKind 等完整元数据
  按原数组位置进入 data-relation-meta.js；
- core + metadata 可逐值重建原始 relations，且重复执行只做结构校验。
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

RELATION_CORE_KEYS = ("from", "to", "rel", "category", "sourceTitle")
_ASSIGN_RE = re.compile(r"^Object\.assign\(DATA,(.*)\);$", re.MULTILINE)
_META_MARKER = "window.__MING_RELATION_META__="


def _compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def read_chunk_payload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = _ASSIGN_RE.search(text)
    if not match:
        raise RuntimeError("找不到 Object.assign(DATA,...)：%s" % path)
    value = json.loads(match.group(1))
    if not isinstance(value, dict):
        raise RuntimeError("DATA chunk 不是对象：%s" % path)
    return value


def _replace_payload(text: str, payload: dict) -> str:
    updated, count = _ASSIGN_RE.subn("Object.assign(DATA,%s);" % _compact(payload), text, count=1)
    if count != 1:
        raise RuntimeError("替换 relations DATA chunk 失败")
    return updated


def split_relation_transport(relations: list[dict]) -> tuple[list[dict], list[dict]]:
    core = []
    metadata = []
    for row in relations:
        visible = {key: copy.deepcopy(row[key]) for key in RELATION_CORE_KEYS if key in row}
        patch = {key: copy.deepcopy(value) for key, value in row.items() if key not in visible}
        core.append(visible)
        metadata.append(patch)
    return core, metadata


def reconstruct_relations(core: list[dict], metadata: list[dict]) -> list[dict]:
    if len(core) != len(metadata):
        raise RuntimeError("关系 core / metadata 长度不一致：%d != %d" % (len(core), len(metadata)))
    result = []
    for visible, patch in zip(core, metadata):
        item = copy.deepcopy(visible)
        item.update(copy.deepcopy(patch))
        result.append(item)
    return result


def _meta_script(metadata: list[dict]) -> str:
    return (
        "window.__MING_RELATION_META__=%s;\n"
        "if(window.__MING_APPLY_RELATION_META__)window.__MING_APPLY_RELATION_META__();\n"
        "window.__MING_DATA_CHUNKS__=window.__MING_DATA_CHUNKS__||{};\n"
        "window.__MING_DATA_CHUNKS__['relation-meta']=true;\n"
        "document.dispatchEvent(new CustomEvent('ming:data-chunk',{detail:{name:'relation-meta'}}));\n"
        % _compact(metadata)
    )


def read_relation_meta(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    start = text.find(_META_MARKER)
    if start < 0:
        raise RuntimeError("relation-meta 格式异常：缺少 registry")
    start += len(_META_MARKER)
    end = text.find(";\n", start)
    if end < 0:
        raise RuntimeError("relation-meta JSON 结束位置异常")
    value = json.loads(text[start:end])
    if not isinstance(value, list):
        raise RuntimeError("relation-meta 必须是数组")
    return value


def check_site(root: Path) -> dict:
    assets = root / "assets"
    relation_path = assets / "data-relations.js"
    meta_path = assets / "data-relation-meta.js"
    if not relation_path.exists():
        raise RuntimeError("缺少 %s" % relation_path)
    if not meta_path.exists():
        raise RuntimeError("缺少 %s" % meta_path)
    payload = read_chunk_payload(relation_path)
    relations = payload.get("relations")
    if not isinstance(relations, list):
        raise RuntimeError("data-relations.js 缺少 relations 数组")
    allowed = set(RELATION_CORE_KEYS)
    for i, row in enumerate(relations):
        extra = set(row) - allowed
        if extra:
            raise RuntimeError("关系 core 仍含 deferred 字段 #%d：%s" % (i, sorted(extra)))
        for key in ("from", "to", "rel", "category", "sourceTitle"):
            if key not in row:
                raise RuntimeError("关系 core 缺少可见字段 #%d：%s" % (i, key))
    metadata = read_relation_meta(meta_path)
    if len(metadata) != len(relations):
        raise RuntimeError("relation-meta 行数与 core 不一致")
    if relations and not any(metadata):
        raise RuntimeError("relation-meta 为空，未保存被拆出的元数据")
    return {
        "relations_bytes": relation_path.stat().st_size,
        "meta_bytes": meta_path.stat().st_size,
        "relation_count": len(relations),
    }


def split_site(root: Path) -> dict:
    assets = root / "assets"
    relation_path = assets / "data-relations.js"
    meta_path = assets / "data-relation-meta.js"
    if not relation_path.exists():
        raise RuntimeError("缺少 %s" % relation_path)
    payload = read_chunk_payload(relation_path)
    relations = payload.get("relations")
    if not isinstance(relations, list):
        raise RuntimeError("data-relations.js 缺少 relations 数组")

    # 已拆分时只验证，不重复生成。
    if meta_path.exists() and all(set(row) <= set(RELATION_CORE_KEYS) for row in relations):
        return check_site(root)

    original = copy.deepcopy(relations)
    core, metadata = split_relation_transport(relations)
    if reconstruct_relations(core, metadata) != original:
        raise RuntimeError("V13 relations core + metadata 不可逆")

    rewritten = dict(payload)
    rewritten["relations"] = core
    relation_path.write_text(
        _replace_payload(relation_path.read_text(encoding="utf-8"), rewritten),
        encoding="utf-8",
    )
    meta_path.write_text(_meta_script(metadata), encoding="utf-8")

    stats = check_site(root)
    final_core = read_chunk_payload(relation_path)["relations"]
    final_meta = read_relation_meta(meta_path)
    if reconstruct_relations(final_core, final_meta) != original:
        raise RuntimeError("V13 物理产物无法恢复原始 relations")
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="V13：拆分 web 关系可见 core 与 deferred metadata")
    parser.add_argument("root", type=Path, nargs="?", default=Path("dist/full"))
    parser.add_argument("--check", action="store_true", help="只检查已拆分产物")
    args = parser.parse_args(argv)
    try:
        stats = check_site(args.root) if args.check else split_site(args.root)
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print("[FAIL] %s" % exc)
        return 1
    print(
        "V13 关系分层通过：core %.1f KiB · metadata %.1f KiB · %d relations"
        % (stats["relations_bytes"] / 1024, stats["meta_bytes"] / 1024, stats["relation_count"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
