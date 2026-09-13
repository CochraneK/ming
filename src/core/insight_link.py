# -*- coding: utf-8 -*-
"""洞察报告 ↔ 实体 的双向索引（构建期一次性生成，前端只消费结果）。

正向：某一节正文里出现了哪些人物 / 地点 / 事件 → 渲染期把这些名字变成可点击链接。
反向：某个人物 / 地点 / 事件被哪几节提到 → 详情页显示「相关洞察」入口。

匹配纪律（对齐项目「宁可留空不可猜错」）：
1. 只做**整名子串**匹配，不做分词/模糊/同义扩展；长度 < 2 的名字一律跳过。
2. 人名取「规范名 + 别名」，地点取「古名 + mentionedAs」，事件取「事件名」；
   命中哪个表面形式就记哪个，前端再用 alias 表映射回规范名（避免张冠李戴）。
3. 命中多少算多少，绝不猜测、绝不补全——没在正文出现的实体不进索引。

导出：
- build_insight_index(chars, locations, events, sections) -> dict
  结构见函数 docstring。
"""
from __future__ import annotations

import re

# 去标签得到纯文本（只用于"是否出现"判断，不改动原始 html）
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

MIN_LEN = 2  # 单字名一律不参与联动（噪声远大于收益）

# 通称/官职/时期词黑名单：这些词在人物表里被当作别名，但它们是**普通名词**，
# 在洞察正文里出现时几乎都不是在指某个具体的人（如「宦官」「给事中」「太平」）。
# 若不过滤，正文里每个「宦官」都会被点成某个人物卡，属于典型的张冠李戴。
# 只列"泛指词"；绰号（九千岁/黑衣宰相）与庙号（太祖/英宗/万历）指向明确，保留。
GENERIC_BLOCK = {
    "宦官", "太监", "太后", "皇后", "皇帝", "太子", "大王", "国王", "大人",
    "大臣", "将军", "首辅", "次辅", "状元", "进士", "举人", "和尚", "道士",
    "百姓", "士兵", "文官", "武将", "义军", "流寇", "叛军", "敌军", "明军",
    "给事中", "副总兵", "总兵", "知府", "巡抚", "知县", "尚书", "侍郎",
    "朝鲜国王",  # 泛指朝鲜君主，非具体人物
    "太平",  # 普通词（天下太平/太平年月）
    "明初", "明末", "明中期",  # 时期词
}


def _plain(html: str) -> str:
    """HTML → 纯文本：去标签 + 压掉所有空白（含换行，避免跨行匹配不到）。"""
    return _WS_RE.sub("", _TAG_RE.sub("", html or ""))


def _surfaces(canonical: str, aliases) -> list[str]:
    """规范名 + 别名，去重、去空白、按长度降序（长名优先，避免短名抢先命中）。"""
    out = []
    for s in [canonical] + list(aliases or []):
        s = _WS_RE.sub("", str(s or ""))
        if len(s) >= MIN_LEN and s not in out and s not in GENERIC_BLOCK:
            out.append(s)
    return sorted(out, key=lambda x: (-len(x), x))


def build_insight_index(chars, locations, events, sections) -> dict:
    """扫描各节正文，产出双向索引。

    返回结构（全部为 JSON 可序列化）：
    {
      "titles":   {sid: 节标题},
      "sections": {sid: {"p": [人名表面形式...], "l": [地名...], "e": [事件名...]}},
      "alias":      {人名表面形式: 规范名},
      "placeAlias": {地名表面形式: 规范古名},
      "byPerson": {规范人名: [sid...]},
      "byPlace":  {规范古名: [sid...]},
      "byEvent":  {事件名: [sid...]},
    }
    """
    # 1) 候选人池：表面形式 -> 规范名
    person_alias: dict[str, str] = {}
    for c in chars:
        name = str(c.get("name") or "").strip()
        if not name:
            continue
        for s in _surfaces(name, c.get("aliases")):
            # 同一表面形式可能指向多人（罕见），以先到者为准，不覆盖避免抖动
            person_alias.setdefault(s, name)

    place_alias: dict[str, str] = {}
    for loc in locations:
        ancient = str(loc.get("ancient") or "").strip()
        if not ancient:
            continue
        for s in _surfaces(ancient, loc.get("mentionedAs")):
            place_alias.setdefault(s, ancient)

    event_names = []
    for ev in events:
        nm = _WS_RE.sub("", str(ev.get("name") or ""))
        if len(nm) >= MIN_LEN and nm not in event_names:
            event_names.append(nm)
    event_names.sort(key=lambda x: (-len(x), x))

    # 2) 逐节扫描
    titles: dict[str, str] = {}
    sec_index: dict[str, dict] = {}
    by_person: dict[str, list] = {}
    by_place: dict[str, list] = {}
    by_event: dict[str, list] = {}

    for sec in sections or []:
        sid = str(sec.get("id") or "")
        if not sid:
            continue
        titles[sid] = str(sec.get("title") or "")
        text = _plain(sec.get("html", ""))
        p_hit, l_hit, e_hit = [], [], []

        for surface, canonical in person_alias.items():
            if surface in text:
                p_hit.append(surface)
                by_person.setdefault(canonical, [])
                if sid not in by_person[canonical]:
                    by_person[canonical].append(sid)

        for surface, canonical in place_alias.items():
            if surface in text:
                l_hit.append(surface)
                by_place.setdefault(canonical, [])
                if sid not in by_place[canonical]:
                    by_place[canonical].append(sid)

        for nm in event_names:
            if nm in text:
                e_hit.append(nm)
                by_event.setdefault(nm, [])
                if sid not in by_event[nm]:
                    by_event[nm].append(sid)

        sec_index[sid] = {
            # 长名优先：前端按此顺序建正则，短名不会抢先截断长名
            "p": sorted(p_hit, key=lambda x: (-len(x), x)),
            "l": sorted(l_hit, key=lambda x: (-len(x), x)),
            "e": sorted(e_hit, key=lambda x: (-len(x), x)),
        }

    return {
        "titles": titles,
        "sections": sec_index,
        "alias": person_alias,
        "placeAlias": place_alias,
        "byPerson": by_person,
        "byPlace": by_place,
        "byEvent": by_event,
    }
