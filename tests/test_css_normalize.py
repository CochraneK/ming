# -*- coding: utf-8 -*-
"""基础 CSS 等价规范化的纯函数回归测试。"""
from __future__ import annotations

import normalize_css as N


def test_css_normalizer_is_idempotent_and_keeps_final_semantics():
    raw = N.CSS.read_bytes()
    cleaned = N.normalize(raw)
    assert cleaned.count(N.QUALITY) == 1
    assert cleaned.count(N.TIP_NOWRAP) == 0
    assert cleaned.count(N.TIP_NORMAL) == 1
    assert cleaned.count(N.TIP_OVERRIDE) == 0
    assert cleaned.count(N.TIP_COMMENT) == 0
    assert N.normalize(cleaned) == cleaned


def test_css_normalizer_is_surgical():
    raw = N.CSS.read_bytes()
    cleaned = N.normalize(raw)
    # 当前历史债只有一个重复质量卡 + 一个 tooltip 覆盖层；若差异突然暴涨，
    # 说明脚本误伤了长 CSS 文件，必须人工复核而不是静默接受。
    assert 0 <= len(raw) - len(cleaned) < 400
