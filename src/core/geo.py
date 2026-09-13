# -*- coding: utf-8 -*-
"""经纬度校验：全项目唯一真源。

禁止 `if not lat or not lng` —— 0 是合法经纬度（赤道/本初子午线），
用真值判断会把 lat=0 的地点误判为"未定位"。
统一改为 `is None` + 类型 + 范围 + NaN 四重检查。
"""
import math

LAT_RANGE = (-90.0, 90.0)
LNG_RANGE = (-180.0, 180.0)


def _as_float(value):
    """把 JSON 里的数字/字符串转成 float；不可转换返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def is_valid_lat(value):
    num = _as_float(value)
    return num is not None and LAT_RANGE[0] <= num <= LAT_RANGE[1]


def is_valid_lng(value):
    num = _as_float(value)
    return num is not None and LNG_RANGE[0] <= num <= LNG_RANGE[1]


def has_coords(lat, lng):
    """两端都合法才算"已定位"。"""
    return is_valid_lat(lat) and is_valid_lng(lng)


def coord_problem(lat, lng):
    """返回 None 表示合法；否则返回人类可读的问题描述（供审计打印）。"""
    if lat is None or lng is None:
        return "缺经纬度（lat=%r, lng=%r）" % (lat, lng)
    lat_num, lng_num = _as_float(lat), _as_float(lng)
    if lat_num is None or lng_num is None:
        return "经纬度非数字（可能是 0 值误判或脏字符串）"
    if not (LAT_RANGE[0] <= lat_num <= LAT_RANGE[1]):
        return "纬度越界 %s" % lat_num
    if not (LNG_RANGE[0] <= lng_num <= LNG_RANGE[1]):
        return "经度越界 %s" % lng_num
    return None
