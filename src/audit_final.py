# -*- coding: utf-8 -*-
"""Ming 终态数据审计：审计对象是**最终模型**，与页面显示同一套口径。

对应《Ming 全面重构方案》P1-05 ~ P1-09：

1. 不再自己读中间文件另算一套口径，而是直接调用生产代码
   `generate_report.build_scope("full")`（以及 p1~p7）拿到最终模型再检查，
   从根上消除「audit 说 561 个地点、页面显示 581 个」这类漂移。
2. 年份判定复用 src/core/year_parser.py，经纬度复用 src/core/geo.py，
   与页面完全一致。
3. 规则分级 INFO / WARNING / ERROR；只要出现 ERROR 就 sys.exit(1)，
   让 CI 能真正拦下坏数据（旧版无论发现什么都 exit 0）。
4. 原 [9] 号规则是 `for ...: pass` 的假实现，这里改成真正的 stale 检查。

用法：
    python src/audit_final.py          # 全量检查
    python src/audit_final.py --quick  # 跳过 p1~p7 分部构建检查
"""
import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from core.geo import coord_problem, has_coords      # noqa: E402
from core.year_parser import has_numeric_year       # noqa: E402

import generate_report as G                          # noqa: E402

INFO, WARNING, ERROR = "INFO", "WARNING", "ERROR"
_SEV_ORDER = {INFO: 0, WARNING: 1, ERROR: 2}

RESULTS = []


def rule(severity, rule_id, message, items=None):
    RESULTS.append({"severity": severity, "id": rule_id, "message": message,
                    "items": list(items or [])})


def load(name):
    with (BASE / "data" / name).open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 规则实现

def check_characters(model):
    """人物主表：id/姓名唯一、非空。"""
    chars = model["characters"]
    names = [c["name"] for c in chars]
    dup = [n for n, c in ((n, names.count(n)) for n in set(names)) if c > 1]
    blank = [n for n in names if not str(n).strip()]
    if dup:
        rule(ERROR, "R-CHAR-01", "人物姓名重复 %d 个" % len(dup), dup[:10])
    if blank:
        rule(ERROR, "R-CHAR-02", "存在空姓名人物 %d 个" % len(blank))
    rule(INFO, "R-CHAR-00", "人物表 %d 人，姓名去重后 %d 人" % (len(chars), len(set(names))))


def check_relations(model):
    """关系：人物端点必须真实存在；不得自环。"""
    chars = {c["name"] for c in model["characters"]}
    dangling, selfloop = [], []
    for r in model["relations"]:
        kinds = r.get("endpointKind") or {}
        for side in ("from", "to"):
            name = r.get(side)
            if (kinds.get(side) or "person") == "person" and name not in chars:
                dangling.append("%s -> %s" % (r["from"], r["to"]))
                break
        if r["from"] == r["to"]:
            selfloop.append(r["from"])
    if dangling:
        rule(ERROR, "R-REL-01", "标为人物但不在人物表的关系端点 %d 处" % len(dangling), dangling[:10])
    if selfloop:
        rule(ERROR, "R-REL-02", "自环关系 %d 条" % len(selfloop), selfloop[:10])
    # 注意：原写法是 `"person" not in (k_from, k_to, "person")`——把 "person" 混进元组后
    # 条件**恒为假**，这条统计永远是 0，还和 R-GRAPH-00 的「排除 72 条」互相矛盾。
    # 正确口径：**任一端点**的类型不是 person（`"person" not in kinds` 会误判成「两端都非人物」）。
    def _kinds(r):
        k = r.get("endpointKind") or {}
        return (k.get("from") or "person", k.get("to") or "person")

    nonperson = sum(1 for r in model["relations"] if _kinds(r) != ("person", "person"))
    rule(INFO, "R-REL-00", "关系 %d 条（其中任一端点非人物 %d 条，与 R-GRAPH-00 排除数应一致）" % (
        len(model["relations"]), nonperson))


def check_graph(model):
    """人物关系图：节点只能是人物；孤立数必须与人物总数自洽。"""
    g = model.get("relationGraphFull") or {}
    stats = g.get("stats") or {}
    nodes = {n["name"] for n in (g.get("nodes") or [])}
    persons = {c["name"] for c in model["characters"]}
    foreign = sorted(nodes - persons)
    if foreign:
        rule(ERROR, "R-GRAPH-01", "人物关系图混入 %d 个非人物节点" % len(foreign), foreign[:10])

    connected = set()
    for r in model["relations"]:
        if r["from"] in persons and r["to"] in persons:
            connected.add(r["from"])
            connected.add(r["to"])
    expect_nodes = len(connected)
    expect_isolated = len(persons) - len(connected)
    ok = (stats.get("nodes") == expect_nodes and stats.get("isolated") == expect_isolated)
    if not ok:
        rule(ERROR, "R-GRAPH-02",
             "关系图口径不一致：节点 %s(应 %d)、孤立 %s(应 %d)" %
             (stats.get("nodes"), expect_nodes, stats.get("isolated"), expect_isolated))
    else:
        rule(INFO, "R-GRAPH-00",
             "关系图 %d 人 / %d 条边；孤立 %d 人（占 %.1f%%）；已排除含非人物端点的关系 %d 条" %
             (stats.get("nodes"), stats.get("edges"), stats.get("isolated"),
              100.0 * stats.get("isolated", 0) / max(len(persons), 1),
              stats.get("excludedNonPerson", 0)))


def check_events(model):
    """未知年份事件：必须用与页面相同的 year_start 判定。"""
    events = model["events"]
    unknown = [e["name"] for e in events if e.get("year_start") is None]
    raw_unknown = [e.get("name") for e in model.get("_raw_events", [])] if model.get("_raw_events") else []
    rule(INFO, "R-EVT-00", "事件 %d 件；可解析出数字年份 %d 件" % (len(events), len(events) - len(unknown)))
    if unknown:
        rule(WARNING, "R-EVT-01", "未知年份事件 %d 件（年份字段非数字，页面按『年份待考』展示）" % len(unknown), unknown)
    # 反向自检：年份字段写得出数字、却没解析出年份 = 解析器漏了
    broken = [e["name"] for e in events
              if e.get("year_start") is None and has_numeric_year(e.get("year"))]
    if broken:
        rule(ERROR, "R-EVT-02", "年份字段含数字但未解析出年份 %d 件（解析器疑漏）" % len(broken), broken[:10])
    if raw_unknown:
        rule(INFO, "R-EVT-03", "原始事件表未知年份 %d 件" % len(raw_unknown))


def check_locations(model):
    """地点：坐标严格校验（None 与 0 必须区分），并统计定位率。"""
    locs = model["locations"]
    bad, unlocated = [], []
    for l in locs:
        lat, lng = l.get("lat"), l.get("lng")
        if lat is None or lng is None:
            unlocated.append("%s(缺坐标)" % l.get("ancient"))
            continue
        problem = coord_problem(lat, lng)
        if problem:
            bad.append("%s: %s" % (l.get("ancient"), problem))
    if bad:
        rule(ERROR, "R-LOC-01", "坐标非法 %d 处" % len(bad), bad[:10])
    rule(INFO, "R-LOC-00", "地点 %d 个；已定位 %d（%.1f%%）；未定位 %d" % (
        len(locs), len(locs) - len(unlocated),
        100.0 * (len(locs) - len(unlocated)) / max(len(locs), 1), len(unlocated)))


def check_geo_stale(model):
    """geo_annotations 与最终地点表的对账（旧版是 `for ...: pass` 假规则）。

    三种情况分开报，避免把"旧称已并入别名"误报成脏数据：
    - 命中地点表原名           → 正常
    - 命中某地点的 mentioned_as（旧称/别名已并入）→ INFO，说明是历史合并
    - 两者都不命中             → WARNING，才是真正悬空的标注
    """
    try:
        geo = load("geo_annotations.json")
    except FileNotFoundError:
        rule(WARNING, "R-GEO-02", "缺少 data/geo_annotations.json，跳过 stale 检查")
        return

    locs = model["locations"]
    names = {l.get("ancient") for l in locs}
    alias_map = {}
    for l in locs:
        for a in (l.get("mentionedAs") or []):
            alias_map.setdefault(a, l.get("ancient"))
    by_name = {l.get("ancient"): l for l in locs}

    stale_hard, merged = [], []
    for g in geo:
        key = g.get("ancient")
        if key in names:
            continue
        if key in alias_map:
            merged.append("%s → %s" % (key, alias_map[key]))
        else:
            stale_hard.append(key)
    if stale_hard:
        rule(WARNING, "R-GEO-01", "geo 标注目标既非地名也非别名，真正悬空 %d 条" % len(stale_hard), stale_hard[:10])
    if merged:
        rule(INFO, "R-GEO-04", "geo 标注使用旧称、已并入地点别名 %d 条（非错误）" % len(merged), merged[:5])

    # 同名异地：同一地名在标注表里有多条不同坐标 → 地点表只能取一个，需人工确认
    by_geo = {}
    for g in geo:
        by_geo.setdefault(g.get("ancient"), []).append(g)
    conflict = []
    for name, items in by_geo.items():
        if name not in by_name:
            continue
        # 占位标注（status=抽取待补）没有坐标字段，float(缺省 0) 会被算成 (0,0)，
        # 与真正的坐标凑成「两个候选」——纯噪声，必须先滤掉再比坐标。
        located = [x for x in items
                   if has_coords(x.get("lat"), x.get("lng"))
                   and not (float(x.get("lat")) == 0.0 and float(x.get("lng")) == 0.0)]
        if len(located) < 2:
            continue
        coords = {(round(float(x.get("lat", 0)), 2), round(float(x.get("lng", 0)), 2)) for x in located}
        if len(coords) > 1:
            detail = " / ".join("%s,%s（%s）" % (x.get("lat"), x.get("lng"), x.get("modern_address", "?")) for x in located)
            conflict.append("%s 有 %d 个候选坐标：%s；地点表采用 %s,%s" % (
                name, len(coords), detail, by_name[name].get("lat"), by_name[name].get("lng")))
    if conflict:
        rule(WARNING, "R-GEO-03", "同名异地未拆分 %d 处（书里是两处不同地点）" % len(conflict), conflict[:10])

    # 坐标不一致（单条标注 vs 地点表）
    mismatch = []
    for g in geo:
        l = by_name.get(g.get("ancient"))
        if not l or not has_coords(l.get("lat"), l.get("lng")):
            continue
        if g.get("ancient") in [c.split(" ")[0] for c in conflict]:
            continue
        if abs(float(l["lat"]) - float(g.get("lat", 0))) > 0.05 or abs(float(l["lng"]) - float(g.get("lng", 0))) > 0.05:
            mismatch.append("%s: 地点表 %s,%s / 标注表 %s,%s" % (
                g.get("ancient"), l.get("lat"), l.get("lng"), g.get("lat"), g.get("lng")))
    if mismatch:
        rule(WARNING, "R-GEO-05", "坐标与标注表不一致 %d 处" % len(mismatch), mismatch[:10])

    rule(INFO, "R-GEO-00", "geo_annotations %d 条：命中原名 %d / 别名并入 %d / 悬空 %d / 同名异地 %d" % (
        len(geo), len(geo) - len(merged) - len(stale_hard), len(merged), len(stale_hard), len(conflict)))


def check_invariants(model):
    """复用 src/validators.py 的结构不变量（构建门禁用的同一份规则）。

    只吸收 ERROR：WARNING/INFO 已在上面按业务语义讲过一遍，重复打印只会淹没
    真正的问题。这样 ``audit_final.py`` 一条命令即覆盖「深审 + 构建门禁」。
    """
    import validators as V

    findings = V.validate_payload(model)
    hard = [f for f in findings if f.severity == V.ERROR]
    others = V.count_by_severity(findings)
    for f in hard:
        rule(ERROR, f.rule, f.message, f.items)
    rule(INFO, "R-INV-00", "结构不变量（validators.py）：ERROR %d / WARNING %d / INFO %d" % (
        others.get(V.ERROR, 0), others.get(V.WARNING, 0), others.get(V.INFO, 0)))


def check_reigns():
    """在位年表：重叠/断档作为 INFO 提示（部分重叠是史实，例如夺门之变）。"""
    try:
        reigns = load("reigns.json")
    except FileNotFoundError:
        return
    rows = sorted(reigns, key=lambda x: x.get("order", 0))
    issues = []
    for prev, cur in zip(rows, rows[1:]):
        if prev.get("end") is None or cur.get("start") is None:
            continue
        if cur["start"] > prev["end"] + 1:
            issues.append("%s→%s 间隔 %d 年" % (prev.get("era"), cur.get("era"), cur["start"] - prev["end"] - 1))
        elif cur["start"] <= prev["end"]:
            issues.append("%s→%s 重叠 %d 年（需人工确认是否史实）" % (prev.get("era"), cur.get("era"), prev["end"] + 1 - cur["start"]))
    if issues:
        rule(INFO, "R-REIGN-01", "在位区间衔接异常 %d 处" % len(issues), issues)
    rule(INFO, "R-REIGN-00", "在位记录 %d 条" % len(rows))


def check_scopes():
    """分部 scope：关系两端必须都落在该部范围内（P1-11 验收）。"""
    for part in ("p1", "p2", "p3", "p4", "p5", "p6", "p7"):
        m = G.build_scope(part)
        names = {c["name"] for c in m["characters"]}
        leak = [r for r in m["relations"] if r["from"] not in names or r["to"] not in names]
        if leak:
            rule(ERROR, "R-SCOPE-01", "%s 关系串范围 %d 条" % (part, len(leak)),
                 ["%s→%s" % (r["from"], r["to"]) for r in leak[:5]])
        else:
            rule(INFO, "R-SCOPE-00", "%s 关系诱导子图干净：%d 人 / %d 条关系" %
                 (part, len(m["characters"]), len(m["relations"])))


# ---------------------------------------------------------------- 汇总输出

def main():
    parser = argparse.ArgumentParser(description="Ming 终态数据审计（对齐最终模型）")
    parser.add_argument("--quick", action="store_true", help="跳过 p1~p7 分部构建检查")
    args = parser.parse_args()

    model = G.build_scope("full")

    print("=" * 68)
    print("Ming 审计 · 对象=最终模型（generate_report.build_scope 输出）")
    print("=" * 68)
    print("范围 %s：章节 %d · 人物 %d · 事件 %d · 关系 %d · 地点 %d（data.json 原始 %d）" % (
        model.get("scopeLabel", model.get("scope")),
        model["metrics"]["chapters"], model["metrics"]["characters"],
        model["metrics"]["events"], model["metrics"]["relations"],
        model["metrics"]["locations"], len(load("data.json").get("locations", []))))
    print()

    check_characters(model)
    check_relations(model)
    check_graph(model)
    check_events(model)
    check_locations(model)
    check_geo_stale(model)
    check_reigns()
    check_invariants(model)
    if not args.quick:
        check_scopes()

    counts = {INFO: 0, WARNING: 0, ERROR: 0}
    worst = INFO
    for r in RESULTS:
        counts[r["severity"]] += 1
        if _SEV_ORDER[r["severity"]] > _SEV_ORDER[worst]:
            worst = r["severity"]
    for sev in (ERROR, WARNING, INFO):
        group = [r for r in RESULTS if r["severity"] == sev]
        if not group:
            continue
        print("[%s] %d 条" % (sev, len(group)))
        for r in group:
            print("  · %s %s" % (r["id"], r["message"]))
            for item in r["items"][:5]:
                print("      - %s" % item)
        print()

    print("-" * 68)
    print("INFO %d · WARNING %d · ERROR %d" % (counts[INFO], counts[WARNING], counts[ERROR]))
    print("=" * 68)
    if counts[ERROR]:
        print("审计失败：存在 %d 条 ERROR，禁止发布。" % counts[ERROR])
        sys.exit(1)
    print("审计通过。")


if __name__ == "__main__":
    main()
