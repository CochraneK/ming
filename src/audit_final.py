# -*- coding: utf-8 -*-
"""明朝项目终态数据审计：跑一遍所有遗留问题检查项，输出可操作的清单。"""
import json, io, os, re, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda n: json.load(io.open(os.path.join(BASE, 'data', n), encoding='utf-8'))

def main():
    data = D('data.json')
    locs = data.get('locations', [])
    chars = data.get('characters', [])
    evs = data.get('events', [])
    rels = data.get('relations', [])
    reigns = D('reigns.json')
    geo = D('geo_annotations.json')

    print('=' * 60)
    print('实体规模：地点 %d / 人物 %d / 事件 %d / 关系 %d / 在位 %d' %
          (len(locs), len(chars), len(evs), len(rels), len(reigns)))

    # 1) 坐标合法性
    bad = [l for l in locs
           if l.get('lat') is not None and (abs(l['lat']) > 90 or abs(l.get('lng') or 0) > 180)]
    print('\n[1] 坐标越界(纬度>90 或 经度>180)：%d' % len(bad))
    for l in bad[:10]:
        print('    -', l.get('ancient'), l.get('lat'), l.get('lng'))

    # 2) 未定位地点
    unloc = [l for l in locs if not l.get('lat') or not l.get('lng')]
    print('\n[2] 未定位地点：%d / %d（定位率 %.1f%%）' %
          (len(unloc), len(locs), 100.0 * (len(locs) - len(unloc)) / max(len(locs), 1)))
    # 按提及次数排序，优先补高频
    unloc.sort(key=lambda x: -len(x.get('chapters', []) or []))
    print('    高频未定位 TOP5：')
    for l in unloc[:5]:
        print('       %s（%d 章）%s' % (l.get('ancient'), len(l.get('chapters') or []),
                                      (l.get('modern') or '')[:20]))

    # 3) 未知年份事件
    unk = [e for e in evs if not e.get('year')]
    print('\n[3] 未知年份事件：%d' % len(unk))
    for e in unk[:10]:
        print('    -', e.get('name'))

    # 4) 关系端点为地点/机构型（非人物）
    names = set(c.get('name') for c in chars)
    loc_names = set(l.get('ancient') for l in locs)
    bad_ep = []
    for r in rels:
        for k in ('from', 'to'):
            v = r.get(k)
            if v and v not in names:
                bad_ep.append((k, v, r.get('rel')))
    cnt = collections.Counter(v for _, v, _ in bad_ep)
    print('\n[4] 关系端点不在人物表：共 %d 处，涉及 %d 个名字' % (len(bad_ep), len(cnt)))
    for v, c in cnt.most_common(8):
        tag = '地点' if v in loc_names else '其他'
        print('    - %s（%s）×%d' % (v, tag, c))

    # 5) 自环
    selfloop = [r for r in rels if r.get('from') == r.get('to')]
    print('\n[5] 自环关系：%d' % len(selfloop))

    # 6) 无章节人物（孤立）
    orphan = [c for c in chars if not (c.get('chapters') or [])]
    print('\n[6] 无章节来源的人物：%d / %d（%.1f%%）' %
          (len(orphan), len(chars), 100.0 * len(orphan) / max(len(chars), 1)))

    # 7) 人物无关系（孤立）
    connected = set()
    for r in rels:
        connected.add(r.get('from')); connected.add(r.get('to'))
    iso = [c for c in chars if c.get('name') not in connected]
    print('\n[7] 无任何关系的人物：%d / %d（%.1f%%）' %
          (len(iso), len(chars), 100.0 * len(iso) / max(len(chars), 1)))

    # 8) 在位区间连续性
    print('\n[8] 在位年表连续性：')
    prev_end = None
    for r in sorted(reigns, key=lambda x: x.get('order', 0)):
        gap = '' if prev_end is None else ('间隔%d年' % (r['start'] - prev_end - 1) if r['start'] > prev_end + 1
                                           else ('重叠%d年' % (prev_end + 1 - r['start']) if r['start'] <= prev_end else '连续'))
        print('    %d. %s %s-%s  %s' % (r.get('order', 0), r.get('era'), r.get('start'), r.get('end'), gap))
        prev_end = r.get('end')

    # 9) geo_annotations stale 条目（目标已不在地点表）
    targets = set()
    for k, v in (geo.items() if isinstance(geo, dict) else []):
        pass
    print('\n[9] geo 标注条目数：%d' % (len(geo) if hasattr(geo, '__len__') else 0))

    # 10) 事件-地点 关联缺失
    no_loc = [e for e in evs if not e.get('location')]
    print('\n[10] 无地点事件：%d / %d' % (len(no_loc), len(evs)))

    print('\n' + '=' * 60)


if __name__ == '__main__':
    main()
