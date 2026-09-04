# -*- coding: utf-8 -*-
"""从全书原文中发现"未被抽取"的潜在人物。

方法：扫所有 2-4 字中文片段 -> 首字须为常见汉姓 -> 排除已知名/别名 ->
排除已知长名的子串(防伪影,如"崇焕"⊂"袁崇焕") -> 排除官职称谓词 ->
按全书频次排序输出候选(出现章节数 + 上下文),供人工判断。

三类强人名信号：
  subj  主语提取：句首/标点后紧跟 说/道/率/攻... 的 2-4 字片段
  appt  封授结构：封/任/拜 X 为...，X 必是人名
  zi    表字结构：X,字Y / X(字Y)，X 是完整人名

运行：
  MODES=zi  TH=1  ...  discover_persons.py   # 只跑表字信号,阈值降到1(最可靠)
  MODES=all TH=3  ...  discover_persons.py   # 三信号全跑,阈值3
  CHAPTERS=p1-c22,p6-c12  ...  discover_persons.py  # 只扫指定章节(针对性核查)
"""
import os, json, re
from collections import Counter, defaultdict

BASE = os.environ.get('BASE') or 'D:/2026/WB项目/明朝'
data = json.load(open(BASE + '/data/data.json', encoding='utf-8'))
chars = data['characters']

# 1) 已知名集合(规范名 + 别名)与"长度>=2的已知名"子串集合
KNOWN = set()
LONG_NAMES = []
for c in chars:
    nm = c.get('name', '')
    if nm:
        KNOWN.add(nm)
        if len(nm) >= 2:
            LONG_NAMES.append(nm)
    for a in (c.get('aliases') or []):
        if a:
            KNOWN.add(a)
            if len(a) >= 2:
                LONG_NAMES.append(a)

KNOWN_SUB = set()
for ln in LONG_NAMES:
    L = len(ln)
    for length in (2, 3, 4):
        for s in range(0, L - length + 1):
            KNOWN_SUB.add(ln[s:s + length])

# 2) 姓氏白名单：标准百家姓 + 增补 + 已知人物名首字
SURNAMES = set('''赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜
戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛
雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪
祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危
江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗
丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳
汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎
祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁
胥能苍双闻莘党翟谭贡劳逢姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农
温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇
广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰
巢关蒯相查后荆红游竺权逮盍益桓公万俟司马上官欧阳夏侯诸葛闻人东方赫连皇甫
尉迟公羊澹台公冶宗政濮阳淳于单于太叔申屠公孙仲孙轩辕令狐钟离宇文长孙慕容
鲜于闾丘司徒司空亓官东郭'''.split())
for c in chars:
    nm = c.get('name', '')
    if nm:
        SURNAMES.add(nm[0])

# 3) 官职/称谓停用词(若候选完全等于或含这些,排除)
TITLE_WORDS = ('王爷', '皇帝', '太子', '公主', '皇后', '贵妃', '妃子', '太监', '宦官', '宫女', '大人',
    '先生', '公子', '将军', '都督', '总兵', '巡抚', '侍郎', '御史', '学士', '状元', '探花', '榜眼',
    '知府', '知县', '县令', '丞相', '宰相', '元帅', '先锋', '参军', '谋士', '谋臣', '武将', '文臣',
    '奸臣', '忠臣', '将领', '尚书', '内阁', '首辅', '大学士', '都尉', '校尉', '千户', '百户', '指挥',
    '太师', '太傅', '太保', '少师', '国公', '郡王', '亲王', '郡主', '郡君', '夫人', '娘娘', '陛下',
    '圣上', '皇上', '今上', '主公', '寨主', '头领', '头目', '帮主', '教主', '掌门', '方丈', '住持')
TITLE_CHARS = set('王帝后妃侯公爵君子公君主嬪嫔卿相帅尉户伯男')
STOP = set(TITLE_WORDS)

# 4) 加载章节正文
chaps = json.load(open(BASE + '/data/chapters.json', encoding='utf-8'))
only = set((os.environ.get('CHAPTERS') or '').split(',')) - {''}
bodies = [(ch.get('key') or ch.get('title', ''), ch.get('body', ''))
          for ch in chaps if ch.get('body') and (not only or (ch.get('key') in only))]
print('章节数(含正文):', len(bodies), ('| 仅扫: ' + ','.join(sorted(only))) if only else '')

# 主语提取
TRIG = re.compile(r'(?:^|[。！？\n\u201c\u201d])\s*([一-龥]{2,4})\s*(说|道|曰|奏|言|问|答|骂|笑|叹|喊|叫|呼|率|领|攻|守|征|击|败|反|起兵|出兵|上书|上疏|回禀|禀报)')
# 封授结构
TRIG2 = re.compile(r'(?:封|拜|立|任|命|以|擢|调|遣|派|令|诛|斩|擒|俘|杀|斩杀)\s*([一-龥]{2,4})\s*(?:为|做|守|征|率|镇|巡抚|总督|尚书|侍郎|将军|大都督|太师|太傅|公|侯|伯|王|相)')
# 表字结构
TRIG3 = re.compile(r'([一-龥]{2,4})\s*[，,（(]\s*字\s*([一-龥]{1,2})')
PRON = set('他他们此人其人这人那人对方自己我你你们我们大家众人人们有人无人彼其咱咱们吾尔汝君公')
freq = Counter()
chapset = defaultdict(set)
ctx = defaultdict(list)
MODES = os.environ.get('MODES', 'all')
RGS = {'subj': TRIG, 'appt': TRIG2, 'zi': TRIG3}
RG_LIST = (TRIG, TRIG2, TRIG3) if MODES == 'all' else tuple(RGS[m] for m in MODES.split(',') if m in RGS)
for key, body in bodies:
    for RG in RG_LIST:
        for m in RG.finditer(body):
            w = m.group(1)
            if w[0] not in SURNAMES:
                continue
            if w in KNOWN:
                continue
            if w in KNOWN_SUB:          # 伪影: 是已知长名的子串
                continue
            if any(ln in w for ln in LONG_NAMES):  # 含已知名(如"朱元璋的"前缀属格)
                continue
            if w in STOP or w in PRON:
                continue
            if any(ch in TITLE_CHARS for ch in w[1:]):  # 含称谓字→官职/称号
                continue
            freq[w] += 1
            chapset[w].add(key)
            if len(ctx[w]) < 3:
                s = max(0, m.start() - 12)
                e = min(len(body), m.end() + 14)
                ctx[w].append(body[s:e].replace('\n', ''))

TH = int(os.environ.get('TH') or 3)
res = [(w, freq[w], len(chapset[w])) for w in freq if freq[w] >= TH]
res.sort(key=lambda x: (-x[1], -x[2]))
print('候选总数(频次>=%d): %d' % (TH, len(res)))
for w, f, cs in res[:90]:
    print('== %s | 频次=%d | 章节=%d' % (w, f, cs))
    for c in ctx[w][:2]:
        print('    …%s…' % c)
