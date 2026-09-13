# -*- coding: utf-8 -*-
"""年份解析：全项目唯一真源。

背景：审计脚本曾用 `if not event.get("year")` 判断"有无年份"，而最终报告
需要的是**可解析成数字的年份**（时间轴要按数值排序）。于是出现
"万历末年"这类字符串——审计认为有年份、报告归入未知年份，两侧数字对不上。

约定：
- `year_bounds(value)` 返回 (start, end) 两个 int，无法解析时返回 (None, None)。
- 一个事件只要 `year_bounds` 两头都为 None，就属于"未知年份"。
  生产与审计都必须调用本函数，不得各自实现。
"""
import re

# 匹配独立的四位年份：1368 / 1644 / 1405
_YEAR_RE = re.compile(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)")


def year_bounds(value):
    """把任意年份字段解析成 (起年, 止年)。

    - None / "" → (None, None)
    - 1368 → (1368, 1368)
    - "1368-1398" / "1368至1398" → (1368, 1398)
    - "万历末年" / "洪武年间" → (None, None)（非数字，属未知年份）
    """
    if value is None or value == "":
        return None, None
    years = [int(x) for x in _YEAR_RE.findall(str(value))]
    if not years:
        return None, None
    return years[0], years[-1]


def has_numeric_year(value):
    """该年份字段是否可解析为数字年份（供审计判定"未知年份"）。"""
    start, _end = year_bounds(value)
    return start is not None
