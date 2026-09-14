# -*- coding: utf-8 -*-
"""V13 关系 core / metadata 分层交付门禁。"""
from __future__ import annotations

import sys
from pathlib import Path

import split_relation_asset_v13 as V13

KIB = 1024
CORE_WARN = 340 * KIB
CORE_HARD = 448 * KIB
META_HARD = 640 * KIB


def human(n: int) -> str:
    return "%.1f KiB" % (n / KIB)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0] if argv else ".ci/site")
    try:
        stats = V13.check_site(root)
    except (RuntimeError, ValueError) as exc:
        print("[FAIL] %s" % exc)
        return 2

    loader_path = root / "assets" / "data-loader.js"
    if not loader_path.exists():
        print("[FAIL] 缺少 data-loader.js")
        return 2
    loader = loader_path.read_text(encoding="utf-8")
    errors = []
    for token in (
        "'relations','relation-meta','time'",
        "relations:['relations']",
        "__MING_APPLY_RELATION_META__",
    ):
        if token not in loader:
            errors.append("loader 缺少 V13 关系分层契约：%s" % token)
    if "relations:['relations','relation-meta']" in loader:
        errors.append("关系索引仍预取 relation-meta")

    core = stats["relations_bytes"]
    meta = stats["meta_bytes"]
    print("V13 relation core：%s · %d relations" % (human(core), stats["relation_count"]))
    print("V13 deferred relation metadata：%s" % human(meta))
    print("V13 关系索引零缓存数据：%s" % human(core))

    if core > CORE_HARD:
        errors.append("data-relations.js 超过 hard %s" % human(CORE_HARD))
    elif core > CORE_WARN:
        print("[WARN] relation core %s > warn %s" % (human(core), human(CORE_WARN)))
    if meta > META_HARD:
        errors.append("data-relation-meta.js 超过 hard %s" % human(META_HARD))

    if errors:
        for error in errors:
            print("[FAIL] %s" % error)
        return 1
    print("V13 关系 core / metadata 分层预算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
