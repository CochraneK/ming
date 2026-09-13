# -*- coding: utf-8 -*-
"""测试公共支撑：路径注入 + payload 惰性缓存。

payload 构建一次约 2 秒，测试之间共享，避免每个用例都重跑聚合。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_cache = {}


def payload(scope: str = "full"):
    """返回指定范围的报告 payload（进程内缓存）。"""
    if scope not in _cache:
        import generate_report as G

        _cache[scope] = G.build_scope(scope)
    return _cache[scope]


def fresh_payload(scope: str = "full"):
    """绕过缓存，用于验证构建的确定性。"""
    import generate_report as G

    return G.build_scope(scope)
