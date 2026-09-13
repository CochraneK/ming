# -*- coding: utf-8 -*-
"""地点「别称」与「书中提及」的分级。

背景：`mentioned_as` 是抽取期从正文里捞出来的「同一地点在书里被怎么称呼 / 被怎么提到」，
它天然混了两种东西：

    真别称  ：塔山、沈阳、两广、延平府、洪都、应天府   ← 可以当「又称」展示
    说明片段：洪承畴籍贯、李成梁镇守、徐阶贬谪之所、
              今辽宁兴城，'山'字型城墙，宁远之战主战场  ← 是「为什么提到这里」，不是名字

前端原来把整个字段统一以「别称：」展示，于是地点卡上会出现
「别称：熊廷弼不守、努尔哈赤退兵错过之关键据点、袁崇焕驻守，高第撤防时唯一不撤之城…」
—— 明显不是别称。这里在**构建期**做一次分级，前端分别渲染成两个字段：

    mentionedAs  原样保留（深链 `?place=` 查找与列表搜索依赖它，不动）
    altNames     真别称（高精度子集，宁缺毋滥）
    context      说明片段

分级策略 = 正向形状约束（必须像地名）+ 负向排除（标点 / 描述词 / 其他实体名 / 今址前缀）。
判不准时一律归到 context——只是换个标题展示，不丢数据。
"""

import re

# 含这些标点基本可以断定是整句说明（斜杠是「多地并列提及」，不算句子，故不列入）
_PUNCT = re.compile(r"[，,、；;：:（）()「」『』“”《》\"']")

# 地名尾字：真别称几乎一定以其中之一收尾（不收尾的现代国名/俗称归 context 无伤大雅）
_TAIL_CHARS = set(
    "府州县卫所关城门山河江湖海岛寺宫殿口桥镇驿堡寨营屯岭谷川原阳阴京都安平"
    "东西南北中村庄苑园监场邑郡路道洲省市店巷街峰"
    # 古称/简称常见收尾（武昌、两广、蓟辽、秦陇…）
    "昌淮辽蓟凉朔肃陕甘云贵闽浙粤晋鲁豫皖湘鄂赣蜀滇黔桂燕赵楚吴越秦陇冀幽并兖青徐荆益广"
)

# 高精度描述词：出现即判为说明片段
_DESC_WORDS = (
    "籍贯", "贬谪", "流放", "充军", "镇守", "驻守", "驻地", "控制区", "防区",
    "所在", "战场", "附近", "一带", "游历", "平叛", "督饷", "改名", "封地",
    "发配", "死守", "自刎", "扎营", "兵败", "之地", "之所", "所辖", "属地",
    "被缉", "被擒", "被围", "被俘", "殉国", "殉难", "遭贬", "任职", "任教",
    "任知", "任巡", "驻节", "粮道", "仓库", "首攻", "首取", "主力",
    "全歼", "退兵", "立足", "集结", "转运", "财路", "封国",
    # 实测捞出来的动作/说明性碎片（结构规则盖不住的）
    "刑场", "内应", "开门", "攻克", "攻占", "决战", "进军", "方向", "总部",
    "编撰", "拥有", "撤入", "退守", "被压缩", "被败", "断流", "押至", "请罪",
    "寻建文", "见高拱", "访空隐", "分兵", "屏蔽", "计划", "全歼", "集团",
)

_MAX_ALT_LEN = 8   # 超过这个长度不可能是地名


def is_context_fragment(text, self_name="", known_names=()):
    """判断一条 mentioned_as 是不是「说明片段」而非真别称。"""
    s = (text or "").strip()
    if not s:
        return True
    if _PUNCT.search(s):                                  # 有标点 → 整句
        return True
    if not (2 <= len(s) <= _MAX_ALT_LEN):                 # 过短/过长 → 不是地名
        return True
    if s[0] in "今明清元宋":
        return True                                       # 「今湖北蕲春」这类是今址，不是别称
    if any(w in s for w in _DESC_WORDS):                  # 含描述词
        return True
    for n in known_names:                                 # 含（或等于）别的实体名
        if n and n != self_name and n in s:
            return True
    if s[-1] not in _TAIL_CHARS:                          # 收尾不像地名
        return True
    return False


def split_mentions(mentioned, self_name="", known_names=()):
    """拆成 (altNames, context)，各自保序去重。"""
    alt, ctx, seen = [], [], set()
    for raw in mentioned or []:
        s = (raw or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        (ctx if is_context_fragment(s, self_name, known_names) else alt).append(s)
    return alt, ctx
