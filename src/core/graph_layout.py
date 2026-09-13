# -*- coding: utf-8 -*-
"""关系图的两种口径（Phase 6 双模式图）与共享的确定性初始布局。

口径分界（这是两种图唯一需要记住的事）：

* **人物图** `build_relation_graph_full`
  方案 A：节点只允许人物表内的实体。端点里的「东林党 / 东厂 / 内阁 / 后金 / 北京」
  等一律不进图（它们仍保留在关系卡片与详情里）。统计口径是
  「人物 N 人 / 人物关系 M 条 / 孤立 K 人」，与页面人物总数自洽。

* **实体图** `build_relation_graph_entities`
  节点 = 全部关系端点（人物 + 地点 + 机构 + 政权 + 其他），按类型着色并给图例。
  统计口径是「实体 N 个 / 关系 M 条」，**不能**再读作「N 名人物」。

两图并存、互不覆盖：默认仍显示人物图，实体图是读者显式选择才出现的第二个视图，
避免读者把实体数量误当成人物数量（这正是方案 P1-01 要防的事）。

两种图共用同一套「按类分扇区 + 扇区内螺旋」的确定性初始坐标（O(n)、无随机、
无 numpy），真正的布局由浏览器端 fullStep() 的实时力模拟完成。
"""
import math

GRAPH_KIND_LABELS = {
    "person": "人物", "place": "地点", "org": "机构",
    "regime": "政权", "other": "其他", "event": "事件",
}


def graph_kind_label(kind: str) -> str:
    return GRAPH_KIND_LABELS.get(kind or "other", "其他")


def _dedupe_edges(relations, idx, category_order=()):
    """把关系折成无向去重边：保留主导类别与该边的关系条数。

    category_order：类别优先级（用于并列时选主导类别），由调用方传入
    `RELATION_CATEGORIES`，避免本模块反向依赖报告层。
    """
    order = {name: i for i, name in enumerate(category_order)}
    groups = {}
    for r in relations:
        a, b = r["from"], r["to"]
        if a == b or a not in idx or b not in idx:
            continue
        i, j = idx[a], idx[b]
        key = (i, j) if i < j else (j, i)
        grp = groups.setdefault(key, {"count": 0, "cats": {}})
        grp["count"] += 1
        cat = r.get("category") or "其他"
        grp["cats"][cat] = grp["cats"].get(cat, 0) + 1
    edges = []
    for (i, j), grp in groups.items():
        # 与原实现逐字等价：先比条数，条数相同时取类别表中**靠后**的那个
        # （未知类别记 99，优先级最高），保证重构图不改变边的配色口径。
        dominant = max(grp["cats"], key=lambda c: (grp["cats"][c], order.get(c, 99)))
        edges.append((i, j, dominant, grp["count"]))
    return edges


def _degree(relations):
    deg = {}
    for r in relations:
        deg[r["from"]] = deg.get(r["from"], 0) + 1
        deg[r["to"]] = deg.get(r["to"], 0) + 1
    return deg


def _deterministic_layout(nodes, deg, bucket_of, canvas_w=1280.0,
                          center_x=680.0, center_y=400.0):
    """按 bucket 分扇区、扇区内螺旋，给每个节点一个确定性初始坐标。

    旧的 Python 力导向布局是 800 轮 × O(n²)（实测让构建超过 110 秒）；这里
    改成 O(n) 的解析式布点——固定算法、无随机数、无第三方依赖，重跑必得同一坐标。
    """
    buckets = {}
    for name in nodes:
        buckets.setdefault(bucket_of(name), []).append(name)
    ordered = sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    total = max(len(nodes), 1)
    placed, angle_cursor = [], -math.pi / 2.0
    for bucket, members in ordered:
        share = len(members) / total
        span = share * 2.0 * math.pi
        members_sorted = sorted(members, key=lambda nm: (-deg[nm], nm))
        count = max(len(members_sorted), 1)
        for k, name in enumerate(members_sorted):
            t = (k + 0.5) / count
            angle = angle_cursor + span * t
            radius = 240.0 + 26.0 * math.sqrt(k + 1) * (1.0 + 4.0 * share)
            placed.append({
                "name": name,
                "bucket": bucket,
                "degree": deg[name],
                "r": round(min(3 + deg[name] ** 0.5 * 1.0, 20), 1),
                "x": center_x + radius * math.cos(angle),
                "y": center_y + radius * 0.62 * math.sin(angle),
            })
        angle_cursor += span

    xs = [nd["x"] for nd in placed]
    ys = [nd["y"] for nd in placed]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    pad = 40.0
    scale = canvas_w / max(maxx - minx, 1.0)
    for nd in placed:
        nd["x"] = round((nd["x"] - minx) * scale + pad, 1)
        nd["y"] = round((nd["y"] - miny) * scale + pad, 1)
    width = canvas_w + 2 * pad
    height = (maxy - miny) * scale + 2 * pad
    return placed, round(max(width, 1.0), 1), round(max(height, 1.0), 1)
