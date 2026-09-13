# -*- coding: utf-8 -*-
"""前端口径与体积预算的回归检查。"""
from __future__ import annotations

import check_budget as CB
import normalize_frontend as NF


def test_insight_metrics_are_dynamic_and_normalizer_is_idempotent():
    sample = "x" + NF.OLD + "y"
    updated = NF.normalize(sample)
    assert NF.OLD not in updated
    assert NF.NEW in updated
    assert NF.normalize(updated) == updated


def test_app_js_no_longer_contains_old_location_count_after_normalization():
    text = NF.APP.read_text(encoding="utf-8")
    normalized = NF.normalize(text)
    assert NF.OLD not in normalized
    assert NF.NEW in normalized
    assert "${metrics.locations} 地点" in normalized


def test_budget_levels_have_warning_headroom_before_hard_failure():
    for name, (warn, hard) in CB.BUDGETS.items():
        assert warn < hard, name
        assert CB.evaluate(name, int(warn))[0] == "OK"
        assert CB.evaluate(name, int(warn) + 1)[0] == "WARNING"
        assert CB.evaluate(name, int(hard) + 1)[0] == "ERROR"
