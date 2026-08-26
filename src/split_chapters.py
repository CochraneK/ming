# -*- coding: utf-8 -*-
"""
《明朝那些事儿》分章解析脚本
----------------------------------
把整本 txt 按「第X部 / 第X章」切成结构化章节，输出 data/chapters.json。
特殊节（引子/尾声/后记/主要参考书目）按出现位置归入相邻部。

设计要点：
- 部标题：第[零壹贰叁肆伍陆柒捌玖拾佰]部 标题
- 章标题：第[零一二三四五六七八九十百零]章 标题（同行）
- 特殊节：引子 / 尾声 / 后记 / 主要参考书目
- 引子出现在第一部之前 → 归入第壹部；尾声归入其当前部；后记/参考书目在末尾归入第柒部
- 正文前的网址声明/书名/简介等归为 frontmatter（不参与抽取）

输出 chapters.json 每条字段：
  key          唯一键（p1=部首 / p1-c1=第1部第1章 / special-引子）
  type         frontmatter | part_header | chapter | special
  part_title   所属部标题（frontmatter 为 null）
  part_index   部序号 1..7（frontmatter 为 0）
  chapter_index 部内章序号（仅 chapter 有值）
  chapter_no   章中文序号（如 "一"）
  chapter_title 章标题
  title        展示标题
  body         正文（已去掉首尾空行）
"""

import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "明朝那些事儿.txt")
OUT = os.path.join(BASE, "data", "chapters.json")

# 中文数字 → int（处理 百/十/零，兼容大小写数字）
_CN = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9,
    '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5, '陆': 6, '柒': 7,
    '捌': 8, '玖': 9,
}
_UNIT = {'十': 10, '拾': 10, '百': 100, '佰': 100}


def cn_to_int(s: str) -> int:
    total = 0
    section = 0
    for ch in s:
        if ch in _UNIT:
            section = (section or 1) * _UNIT[ch]
            total += section
            section = 0
        else:
            section = _CN.get(ch, 0)
    total += section
    return total


PART_RE = re.compile(r'^第([零壹贰叁肆伍陆柒捌玖拾佰]+)部\s*(.+?)\s*$')
CHAPTER_RE = re.compile(r'^第([零一二三四五六七八九十百零壹贰叁肆伍陆柒捌玖拾佰]+)章\s*(.*?)\s*$')
SPECIAL_RE = re.compile(r'^(引子|尾声|后记|主要参考书目)\s*$')

SPECIALS = ['引子', '尾声', '后记', '主要参考书目']


def find_source():
    if os.path.exists(SRC):
        return SRC
    raise FileNotFoundError(f"找不到源文件：{SRC}")


def main():
    src = find_source()
    print(f"[info] 源文件: {src}")

    with open(src, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    entries = []
    current_part_title = None
    current_part_index = 0
    chapter_counter = {}  # part_index -> 章序号计数
    cur = None

    def flush():
        nonlocal cur
        if cur is not None:
            # 去掉首尾空行
            body_lines = cur['_raw']
            while body_lines and body_lines[0].strip() == '':
                body_lines.pop(0)
            while body_lines and body_lines[-1].strip() == '':
                body_lines.pop()
            cur['body'] = '\n'.join(body_lines)
            del cur['_raw']
            entries.append(cur)
            cur = None

    in_body = False  # 是否进入正文（========正文======== 之后）
    for raw in lines:
        line = raw.rstrip('\n')
        stripped = line.strip()

        # 标记正文开始
        if stripped.startswith('========正文') or stripped == '========正文========':
            in_body = True
            continue
        if not in_body:
            # 正文前的所有内容累积到 frontmatter
            if cur is None or cur['type'] != 'frontmatter':
                flush()
                cur = {
                    'type': 'frontmatter',
                    'part_title': None,
                    'part_index': 0,
                    'chapter_index': None,
                    'chapter_no': None,
                    'chapter_title': None,
                    'title': 'frontmatter',
                    '_raw': [],
                }
            cur['_raw'].append(line)
            continue

        # 正文区：匹配 部 / 章 / 特殊节
        m_part = PART_RE.match(stripped)
        m_chap = CHAPTER_RE.match(stripped)
        m_special = SPECIAL_RE.match(stripped)

        if m_part:
            flush()
            idx = cn_to_int(m_part.group(1))
            title = m_part.group(2).strip()
            current_part_index = idx
            current_part_title = f"第{m_part.group(1)}部 {title}"
            chapter_counter[idx] = 0
            cur = {
                'type': 'part_header',
                'part_title': current_part_title,
                'part_index': idx,
                'chapter_index': None,
                'chapter_no': None,
                'chapter_title': None,
                'title': current_part_title,
                '_raw': [],
            }
        elif m_chap:
            flush()
            cn_no = m_chap.group(1)
            cidx = cn_to_int(cn_no)
            title = m_chap.group(2).strip()
            chapter_counter.setdefault(current_part_index, 0)
            chapter_counter[current_part_index] += 1
            cur = {
                'type': 'chapter',
                'part_title': current_part_title,
                'part_index': current_part_index,
                'chapter_index': chapter_counter[current_part_index],
                'chapter_no': cn_no,
                'chapter_title': title,
                'title': f"第{cn_no}章 {title}",
                '_raw': [],
            }
        elif m_special:
            flush()
            name = m_special.group(1)
            # 引子在第一部之前 → 归入第壹部
            if name == '引子' and current_part_title is None:
                part_title = '第壹部 洪武大帝'
                part_index = 1
            else:
                part_title = current_part_title
                part_index = current_part_index
            cur = {
                'type': 'special',
                'part_title': part_title,
                'part_index': part_index,
                'chapter_index': None,
                'chapter_no': None,
                'chapter_title': None,
                'title': name,
                '_raw': [],
            }
        else:
            # 普通正文行，归入当前 entry
            if cur is None:
                # 正文开始但还没遇到任何标记（理论上不应发生）
                cur = {
                    'type': 'frontmatter',
                    'part_title': current_part_title,
                    'part_index': current_part_index,
                    'chapter_index': None,
                    'chapter_no': None,
                    'chapter_title': None,
                    'title': 'unknown',
                    '_raw': [],
                }
            cur['_raw'].append(line)

    flush()

    # 生成 key
    part_seen = {}
    for e in entries:
        if e['type'] == 'part_header':
            part_seen[e['part_index']] = part_seen.get(e['part_index'], 0) + 1
            e['key'] = f"p{e['part_index']}"
        elif e['type'] == 'chapter':
            e['key'] = f"p{e['part_index']}-c{e['chapter_index']}"
        elif e['type'] == 'special':
            e['key'] = f"special-{e['title']}"
        else:
            e['key'] = f"frontmatter"

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    # 统计报告
    from collections import Counter
    type_count = Counter(e['type'] for e in entries)
    print(f"[done] 共切分 {len(entries)} 个单元")
    for t, c in type_count.items():
        print(f"       {t}: {c}")
    # 特殊节归属
    print("[special 归属]")
    for e in entries:
        if e['type'] == 'special':
            print(f"       {e['title']:8s} -> {e['part_title']}")
    # 各部章数
    print("[各部章数]")
    for e in entries:
        if e['type'] == 'part_header':
            cnt = sum(1 for x in entries if x['type'] == 'chapter' and x['part_index'] == e['part_index'])
            print(f"       {e['part_title']:18s} -> {cnt} 章")


if __name__ == '__main__':
    main()
