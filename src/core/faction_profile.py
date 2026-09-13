# -*- coding: utf-8 -*-
"""人物势力/身份字段的结构化解析：全项目唯一真源（P2-03）。

背景
----
`data.json` 的 `characters[].faction` 是抽取产物，把「政权 · 时期 · 派系 · 身份类别 ·
官职 · 籍贯 · 科举 · 备注」全揉进一个字符串——1231 个人物产生 473 个互不相同的串：

    "明朝"                        "明朝·阉党"
    "明朝·嘉靖朝·文官"             "明朝·内阁首辅（浙党）"
    "建州女真·后金开国汗（嘉靖三十八年1559生赫图阿拉）"
    "明朝·兵科给事中（湖广应山人，万历三十五年1607进士）"

于是前端只能靠正则猜字段含义（`cleanCardFields()`）。本模块把这一串**一次性**解析成
结构化字段；生产构建（generate_report）、校验（validators）与前端共用同一份结果。

设计原则
--------
1. **宁可留空，不可猜错**：没有明确表述的字段一律 None / 空列表。
   （例如 `jinshi_year` 只在出现「xx年进士」这类说法时才给出。）
2. 词表驱动，不写散落正则：分类依据是显式 token 表，新增脏串只需补词表。
3. 未经归类的残料一律进 `note`，绝不丢弃——原串永远能从 `raw` 完整回查。
4. 纯函数、可复现：同输入必得同输出，供构建与单测共用。

返回结构
--------
    {
      "raw":         "明朝·兵科给事中（湖广应山人，万历三十五年1607进士）",
      "label":       "兵科给事中",   # 卡面「势力」标签：派系 > 身份 > 机构 > 官职 > 政权
      "regime":      "明朝",         # 原样的势力/政权主体
      "dynasty":     "明",           # 归一朝代短名
      "period":      "万历朝",        # 时期（年号朝）
      "factions":    [],             # ["东林党"]，真正的政治派系
      "orgs":        [],             # ["内阁"]，机构/衙门
      "categories":  ["言官"],        # 身份类别
      "office":      ["兵科给事中"],   # 官职
      "origin":      "湖广应山",      # 籍贯（仅在有明确「…人」表述时）
      "jinshi_year": 1607,           # 科举中式年份（公元，仅在明确表述时）
      "note":        None,           # 其余括号备注
    }
"""
import re

# ----------------------------------------------------------------- 词表
# 时期：年号 + 朝/年间。年号表由调用方从 data.json 的 reigns 传入（reign_years），
# 本模块只负责识别「像时期」的写法，避免内置一份可能过期的年号表。
_PERIOD_RE = re.compile(r"^([\u4e00-\u9fa5]{2})(朝|年间|朝年间)?$")

# 势力 / 政权主体 → 归一朝代短名。长 token 必须排在前面（"明朝" 先于 "明"）。
REGIME_TO_DYNASTY = (
    ("建文朝廷", "明"), ("建文朝", "明"), ("明朝", "明"), ("南明", "明"),
    ("朱元璋军", "明"), ("燕王", "明"), ("明朝军", "明"), ("淮西集团", "明"),
    ("浙东集团", "明"), ("陕西地主武装", "明"), ("宁王", "明"),
    ("北元", "元"), ("元朝", "元"), ("元军", "元"),
    ("后金", "后金"), ("清朝", "清"),
    ("蒙古", "蒙古"), ("瓦剌", "蒙古"), ("鞑靼", "蒙古"),
    ("建州女真", "女真"), ("海西女真", "女真"),
    ("日本", "日本"), ("日军", "日本"), ("战国大名", "日本"),
    ("朝鲜", "朝鲜"), ("高丽", "高丽"), ("安南", "安南"), ("渤林邦", "渤泥"),
    ("葡萄牙", "葡萄牙"), ("普鲁士", "普鲁士"), ("法国", "法国"),
    ("红巾军", "红巾军"), ("天完", "天完"),
    ("张士诚", "张士诚"), ("陈友谅军", "陈友谅"),
    ("民变", "民变"), ("起义", "民变"), ("民间", "民间"), ("平民", "民间"),
    ("南宋", "宋"), ("东晋", "晋"), ("东吴", "吴"), ("三国", "三国"),
    ("后晋", "后晋"), ("春秋", "春秋"), ("汉朝", "汉"), ("汉", "汉"),
    ("唐朝", "唐"), ("明", "明"), ("元", "元"), ("清", "清"), ("宋", "宋"),
    ("唐", "唐"), ("民", "民间"),
)

# 真派系（政治阵营）。这是本书最重要的线索，卡面优先显示。
FACTION_TOKENS = (
    "东林党", "东林学人", "东林", "阉党", "浙党", "楚党", "齐党", "宣党", "昆党",
    "三党", "严党", "胡党", "高党", "张门生", "徐阶系", "反对派", "八虎",
    "心学", "王学", "泰州学派", "复社", "清流",
)

# 机构 / 衙门。
ORG_TOKENS = (
    "内阁大学士", "内阁首辅", "内阁次辅", "内阁", "朝廷", "都察院", "大理寺",
    "六科", "六部", "吏部", "户部", "礼部", "兵部", "刑部", "工部", "通政司",
    "兵部职方司", "职方司", "翰林院", "翰林", "司礼监", "御用监", "尚膳监",
    "光禄寺", "太医院", "国子监", "钦天监", "锦衣卫", "东厂", "西厂",
    "东江镇", "神机营", "三千营", "五军都督府", "中军都督府", "南京中军都督府",
    "文渊阁", "东阁", "谨身殿", "藩王府", "王府", "辽王府", "卫所", "都司",
)

# 身份类别（不含派系与机构）。
CATEGORY_TOKENS = (
    "文官", "官僚", "武将", "武官", "军", "军事", "将", "将领", "水军将领",
    "海军将领", "边将", "边军", "守将", "部将", "总兵", "副总兵", "铁骑统将",
    "宦官", "内臣", "太监", "御史", "言官", "给事中", "皇室", "皇长子", "太子",
    "后宫", "宫女", "嫔妃", "宗室", "藩王", "外戚", "文人", "秀才", "庶吉士",
    "科举", "地方官", "幕僚", "降官", "海盗", "走私海盗", "强盗", "混混",
    "地方恶霸", "恶霸", "平民", "民间", "道士", "方外", "佞幸", "奸臣", "汉奸",
    "使者", "使臣", "外交", "翻译", "医", "商人", "地主", "土司", "叛军",
    "首领", "头领",
    "贝勒", "大名", "关白", "监军", "清官", "首辅", "阁员", "将军", "校尉",
    "官吏", "水利", "航海家",
)

# 官职：以「官职尾词」为核心，向左吞 0~6 个汉字的前缀（如「辽东副总兵」「兵科给事中」）。
_OFFICE_RE = re.compile(
    r"[\u4e00-\u9fa5]{0,6}?"
    r"(?:尚书|侍郎|都御史|御史|给事中|巡抚|总督|总兵|副总兵|参将|游击将军|"
    r"经略|巡按|监军|副使|知府|知县|知州|主事|员外郎|郎中|大学士|首辅|次辅|"
    r"编修|检讨|庶吉士|佥事|指挥使|都督|布政使|按察使|少卿|寺丞|秉笔|太监|"
    r"监正|推官|留守|镇守|侍读|侍讲|祭酒|司业|中书|舍人|都指挥)"
)

# 籍贯：以行政区划词或省级前缀开头的「…人」表述。
_PROVINCE_PREFIX = (
    "浙江", "江西", "湖广", "河南", "山东", "山西", "陕西", "四川", "福建",
    "广东", "广西", "云南", "贵州", "直隶", "南直隶", "北直隶", "辽东",
    "江苏", "安徽", "河北", "甘肃", "宁夏", "湖北", "湖南", "江南",
)
# 「…人」不做行首断言（籍贯常出现在句中「，湖广应山人，」），但要求前字不是标点、
# 且整体不能是「人民」这类词。
_ORIGIN_RE = re.compile(r"[\u4e00-\u9fa5]{2,10}人(?![民])")
# 以这些字收尾的「…人」是身份/关系词，不是籍贯：门人、家人、友人、商人、学人、
# 旧人、联系人、合伙人……（取自 data.json 里真实出现过的全部形态）
_ORIGIN_STOP_CHARS = set("门伙友家商学旧系主亲仆属眷员工兵农奴夷僧道儒臣官徒党卒")
# 无省级前缀时的可接受长度：明代籍贯常只写府/县名（宁波人、无锡人、山阴人）。
_ORIGIN_BARE_MAX = 4

# 科举：「万历三十五年1607进士」/「隆庆二年进士」/「1607 进士」
_JINSHI_PLAIN_RE = re.compile(r"(?<!\d)(1[3-6]\d{2})(?!\d)\s*年?\s*进士")
_JINSHI_ERA_RE = re.compile(
    r"(洪武|建文|永乐|洪熙|宣德|正统|景泰|天顺|成化|弘治|正德|嘉靖|隆庆|万历|"
    r"泰昌|天启|崇祯)([〇零一二三四五六七八九十元]{1,4})年进士"
)
_ERA_NUM = {"〇": 0, "零": 0, "元": 1, "一": 1, "二": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

# 政权前缀剥离：处理「明朝宗室」「明朝军」「明朝言官」这类拼接串。
_REGIME_PREFIXES = ("明朝", "清朝", "元朝", "后金", "蒙古", "日本", "朝鲜",
                    "建州女真", "海西女真")

# role 里出现派系名时，只有这些「自我认同」句式才算数——否则
# 「被东林借杨镐事攻击」这类叙述会被误判成东林党人。
_FACTION_SELF_RE = re.compile(
    r"(?:^|[，。；、（])%s(?:党人|党|人|名士|要角|成员|门人|传人|弟子|插班生|领袖|"
    r"首辅|骨干|中坚|一脉|一派|同乡|派|徒)"
)
# 官职最短 2 字（「御史」「巡抚」「太监」都是 2 字，尾词表已保证不会是碎片）。
_MIN_OFFICE_LEN = 2


def _han_to_int(text: str):
    """把「三十五」「二」「十」转成 int；无法解析返回 None。

    只覆盖年号纪年的实际写法（1~99），不做通用中文数字解析。
    """
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "十" in text:
        head, _, tail = text.partition("十")
        tens = _ERA_NUM.get(head, 1) if head else 1
        ones = _ERA_NUM.get(tail, 0) if tail else 0
        if tens is None or ones is None:
            return None
        return tens * 10 + ones
    return _ERA_NUM.get(text)


def _split_head_and_parens(raw: str):
    """拆出括号外主串与括号内各项。"""
    head, parens = raw, []
    m = re.search(r"[（(]", raw)
    if m:
        head = raw[:m.start()]
        for inside in re.findall(r"[（(]([^（()）]*)[)）]", raw):
            inside = inside.strip()
            if inside:
                parens.append(inside)
    return head.strip(), parens


def _classify_token(token: str, out: dict, era_names=()) -> bool:
    """把一个 token 归类写进 out（就地修改）。返回是否归类成功。

    era_names：已知年号元组，用于识别「嘉靖朝内阁」这类「时期+机构」拼接。
    """
    token = token.strip()
    if not token:
        return True
    if token in FACTION_TOKENS:
        _add(out["factions"], "东林党" if token.startswith("东林") else token)
        return True
    if token in ORG_TOKENS:
        _add(out["orgs"], token)
        return True
    if token in CATEGORY_TOKENS:
        _add(out["categories"], token)
        return True
    # 精确政权名优先于「时期+XX」拆分——否则「建文朝廷」会被 建文+朝廷 误拆成时期
    for name, dynasty in REGIME_TO_DYNASTY:
        if token == name:
            if out["regime"] is None:
                out["regime"] = token
                out["dynasty"] = dynasty
            return True
    # 「嘉靖朝内阁」这类「时期+机构/身份」拼接：拆开各自归类。
    # 仅当后缀本身是已知 token 时才拆，避免误伤（建文朝廷、正统年间…）。
    for era in era_names:
        if not token.startswith(era):
            continue
        rest = token[len(era):]
        if rest in ("", "朝", "年间", "朝年间"):
            if out["period"] is None:
                out["period"] = era + "朝"
            return True
        if rest.startswith("朝"):
            tail = rest[1:]
            if tail in ORG_TOKENS or tail in CATEGORY_TOKENS or tail in FACTION_TOKENS:
                if out["period"] is None:
                    out["period"] = era + "朝"
                return _classify_token(tail, out, era_names)
    period = _PERIOD_RE.match(token)
    if period and period.group(2):
        if out["period"] is None:
            out["period"] = token
        return True
    for prefix in _REGIME_PREFIXES:
        if token.startswith(prefix) and len(token) > len(prefix):
            if out["regime"] is None:
                out["regime"] = prefix
                out["dynasty"] = dict(REGIME_TO_DYNASTY).get(prefix)
            return _classify_token(token[len(prefix):], out, era_names)
    offices = [m.group(0).strip() for m in _OFFICE_RE.finditer(token)]
    offices = [o for o in offices if len(o) >= _MIN_OFFICE_LEN]
    if offices:
        for office in offices:
            _add(out["office"], office)
        return True
    return False


def _add(seq: list, value: str):
    if value and value not in seq:
        seq.append(value)


def _add_all(seq: list, values):
    for value in values or ():
        _add(seq, value)


def _scan_factions(text: str, out: dict):
    """在自由文本（role）里补扫派系名，仅认「自我认同」句式。

    role 常把派系写在身份描述里（「浙党首辅」「王锡爵学生，东林党要角」），
    只解析 faction 串会漏；但叙述句（「被东林借杨镐事攻击」）不能算。
    """
    _add_all(out["factions"], factions_from_role(text))


def factions_in(text: str) -> list:
    """宽松扫描：文本里出现派系名即算（用于「势力」字段本身，该字段本就是标签）。"""
    found, joined = [], text or ""
    for token in sorted(FACTION_TOKENS, key=len, reverse=True):
        if token in joined:
            _add(found, "东林党" if token.startswith("东林") else token)
            joined = joined.replace(token, "")
    return found


def factions_from_role(text: str) -> list:
    """严格扫描：只认「自我认同」句式，避免把别人的阵营算到自己头上。"""
    found, joined = [], text or ""
    for token in sorted(FACTION_TOKENS, key=len, reverse=True):
        if token not in joined:
            continue
        pattern = re.compile(_FACTION_SELF_RE.pattern % re.escape(token))
        if pattern.search(joined):
            _add(found, "东林党" if token.startswith("东林") else token)
            joined = joined.replace(token, "")
    return found


def _extract_origin(text: str, relaxed: bool = False):
    """从一段文字里抽取籍贯。

    relaxed=False（用于 role 这类自由叙述）：必须有省级前缀或 县/府/州/卫/镇 结尾；
    relaxed=True（只用于括号内的籍贯字段）：额外接受 2~4 字的府县名（宁波人、无锡人）。
    自由叙述里放宽会把「…三人」「…成人」之类误判成籍贯，所以两档分开。
    """
    for m in _ORIGIN_RE.finditer(text or ""):
        body = m.group(0)[:-1]
        if not 2 <= len(body) <= 8:
            continue
        if body[-1] in _ORIGIN_STOP_CHARS:
            continue
        if body.startswith(("生意", "乡下", "读书", "蒙古", "汉", "满")):
            continue
        if body.startswith(_PROVINCE_PREFIX) or re.search(r"(县|府|州|卫|镇)$", body):
            return body
        if relaxed and len(body) <= _ORIGIN_BARE_MAX:
            return body
    return None


def _extract_jinshi(text: str, reign_years=None):
    """抽取科举中式年份（公元）。优先显式四位年，其次年号 + 汉数。"""
    plain = _JINSHI_PLAIN_RE.search(text or "")
    if plain:
        return int(plain.group(1))
    era = _JINSHI_ERA_RE.search(text or "")
    if era:
        num = _han_to_int(era.group(2))
        starts = (reign_years or {}).get(era.group(1))
        if num and starts:
            return starts + num - 1
    return None


def parse_profile(faction_raw, role="", reign_years=None) -> dict:
    """把 faction 原始串 + role 解析为结构化 profile（纯函数）。

    reign_years: {年号: 元年公元}，由调用方从 data.json 的 reigns 传入，
    避免本模块内置一份可能与报告口径不一致的年号表。
    """
    raw = (faction_raw or "").strip()
    out = {
        "raw": raw, "label": "", "regime": None, "dynasty": None, "period": None,
        "factions": [], "orgs": [], "categories": [], "office": [],
        "origin": None, "jinshi_year": None, "note": None,
    }
    era_names = tuple((reign_years or {}).keys())
    head, parens = _split_head_and_parens(raw)

    leftovers = [t for t in re.split(r"[·・，,、/\s]+", head)
                 if t and not _classify_token(t, out, era_names)]
    for inside in parens:
        for part in re.split(r"[，,、/]", inside):
            part = part.strip()
            if not part or _classify_token(part, out, era_names):
                continue
            # 籍贯与科举统一在下面抽取，不再当作备注
            if _extract_origin(part) or _extract_jinshi(part, reign_years):
                continue
            leftovers.append(part)

    # 籍贯 / 科举：括号内找不到就从 role 里再找一次（role 用严格档，避免误判）
    inside_text = "，".join(parens)
    out["origin"] = _extract_origin(inside_text, relaxed=True) or _extract_origin(role)
    out["jinshi_year"] = _extract_jinshi(inside_text, reign_years) \
        or _extract_jinshi(role, reign_years)

    # 官职：role 的首个小句通常就是官职（「兵部左侍郎（后主角）」）
    if not out["office"] and role:
        first_clause = re.split(r"[，。；;：:]", role.strip())[0]
        for office in (m.group(0).strip() for m in _OFFICE_RE.finditer(first_clause)):
            if len(office) >= _MIN_OFFICE_LEN:
                _add(out["office"], office)

    _scan_factions(role, out)

    out["note"] = "；".join(x for x in leftovers if len(x) >= 2) or None
    # 卡面「势力」标签：派系 > 身份类别 > 机构 > 官职 > 政权 > 原串
    for key in ("factions", "categories", "orgs", "office"):
        if out[key]:
            out["label"] = out[key][0]
            break
    else:
        out["label"] = out["regime"] or raw or "势力待补"
    return out


def reign_start_map(reigns) -> dict:
    """从 data.json 的 reigns 构造 {年号: 元年公元}，供科举年份换算。"""
    table = {}
    for item in reigns or []:
        era, start = item.get("era"), item.get("start")
        if era and isinstance(start, int):
            table.setdefault(era, start)
    return table


def profile_stats(profiles) -> dict:
    """覆盖率统计，供审计与验收引用（不做门禁，只如实报告）。"""
    total = len(profiles)
    filled = {
        "faction": sum(1 for p in profiles if p.get("factions")),
        "category": sum(1 for p in profiles if p.get("categories")),
    }
    for key in ("regime", "dynasty", "office", "origin", "jinshi_year"):
        filled[key] = sum(1 for p in profiles if p.get(key))
    unclassified = sum(1 for p in profiles if not (
        p.get("factions") or p.get("orgs") or p.get("categories")
        or p.get("regime") or p.get("office")
    ))
    return {"total": total, "filled": filled, "unclassified": unclassified}
