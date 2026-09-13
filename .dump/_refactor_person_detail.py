# -*- coding: utf-8 -*-
"""Phase 6 前置重构：把两处重复的「人物详情」内联 HTML 收敛为 showPerson()。

app.js 里有两处几乎相同的人物详情模板（人物页的「详情」按钮、年谱里的人物名），
其中一处多一个「关系」区块。这里统一成一个 personDetailHTML(x)，调用点改为
showPerson(x.name)；后续 deep link 也复用它。
幂等：已重构过则直接退出。
"""
import io
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
P = BASE / "web" / "js" / "app.js"
src = io.open(P, encoding="utf-8").read()

if "function personDetailHTML" in src:
    print("already refactored")
    raise SystemExit(0)

CALL = "openDetail(x.name,"
SUFFIX = "`);bindEventNameClicks()"
out = []
i = 0
count = 0
while True:
    j = src.find(CALL, i)
    if j < 0:
        out.append(src[i:])
        break
    k = src.find(SUFFIX, j)
    if k < 0:
        raise SystemExit("找不到调用结尾，中止")
    out.append(src[i:j])
    out.append("showPerson(x.name)")
    count += 1
    i = k + len(SUFFIX)
new = "".join(out)
if count != 2:
    raise SystemExit("预期 2 处调用，实际 %d 处，中止" % count)

DETAIL = '''/* 人物详情：唯一实现。人物页「详情」按钮、年谱人物名、URL deep link 共用，
   避免同一张卡在三个地方各写一份模板而慢慢长歪。 */
function personDetailHTML(x){
 const relHtml=(x.relations||[]).length?x.relations.map(r=>`<span class="rel ${r.dir}">${r.dir==='in'?'←':'→'} ${r.dir==='in'?esc(r.other)+' '+esc(r.rel):esc(r.rel)+' '+esc(r.other)}</span>${epTag(r.other,r.otherKind)}`).join('、'):'无';
 return `<div class="detail-grid"><div class="detail-block"><strong>身份</strong><p>${esc(x.role)}</p></div><div class="detail-block"><strong>势力</strong><p>${esc(x.faction||'未标注')}</p></div><div class="detail-block"><strong>生卒 / 籍贯</strong><p>${esc(x.life)} · ${esc(x.birth)}</p></div><div class="detail-block"><strong>状态</strong><p>${esc(x.status)}</p></div><div class="detail-block detail-wide"><strong>别名</strong><p>${esc((x.aliases||[]).join('、')||'无')}</p></div><div class="detail-block detail-wide"><strong>涉及事件（${x.events.length}）</strong>${x.events.length?`<ul class="event-list">${x.events.slice(0,12).map(n=>`<li><button class="link-button" data-event-name="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul>`:`<p class="muted">书中未作为事件参与者出现。</p>`}</div><div class="detail-block detail-wide"><strong>同章上下文事件（${x.contextEvents.length}）</strong>${x.contextEvents.length?`<ul class="event-list">${x.contextEvents.slice(0,15).map(n=>`<li><button class="link-button" data-event-name="${esc(n)}">${esc(n)}</button></li>`).join('')}</ul><p class="muted">书中同章提及，非本人物直接参与（可作关联线索）</p>`:`<p class="muted">同章亦无其它事件记录。</p>`}</div><div class="detail-block detail-wide"><strong>关系</strong><p>${relHtml}</p></div><div class="detail-block detail-wide"><strong>来源章节</strong><div class="source-row">${chapterChips(x.chapters.map(k=>({key:k,...DATA.chapters[k]})))}</div></div>${x.derivedCount?`<div class="detail-block detail-wide"><strong>出场口径</strong><p>共 ${x.chapters.length} 章，其中 ${x.derivedCount} 章为文本反查推导（本章正文出现至少 6 次自动登记，与 LLM 抽取区分）</p></div>`:''}</div>`;
}
function showPerson(name){
 const x=DATA.characters.find(y=>y.name===name);if(!x)return false;
 openDetail(x.name,personDetailHTML(x));bindEventNameClicks();
 writeHash({view:state.view,person:x.name,detail:'1'});
 return true;
}
'''

anchor = "function openDetail(title,html){"
pos = new.find(anchor)
if pos < 0:
    raise SystemExit("找不到 openDetail 定义，中止")
new = new[:pos] + DETAIL + new[pos:]

io.open(P, "w", encoding="utf-8", newline="").write(new)
print("refactored: %d 处调用 → showPerson()，新增 personDetailHTML/showPerson" % count)
