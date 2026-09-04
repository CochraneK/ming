# -*- coding: utf-8 -*-
"""
============================================================================
明朝那些事儿 · 自动五元组抽取脚本（在【用户本机】运行）
============================================================================
用途：
    遍历 chapters.json 中尚未抽取的章节，调用本机 OmniRoute 网关里的
    【免费模型】（如 hy3）按"角色/地点/事件/关系/时间"五维抽取，
    自动合并进 data/extract_raw.json 并重新生成 data/data.json。

为什么在用户本机跑？
    本脚本通过 http://localhost:20128（OmniRoute 本地网关）调用模型。
    WorkBuddy 沙箱与本机 loopback 隔离，连不上本机网关，因此请在
    你自己装了 OmniRoute 的电脑上运行本脚本（项目和 OmniRoute 同机）。

运行前准备：
    1) 打开 OmniRoute 桌面版，确认它正在运行（仪表盘 http://localhost:20128）。
    2) 在仪表盘确认有一个【免费】模型已启用（例如 hy3）。
       想看有哪些模型可用，可在本机终端执行：
         curl http://localhost:20128/v1/models
       把返回里的 id（如 "hy3"）填到下面 CONFIG 的 MODEL。
    3) 用本机 Python 运行（无需联网、无需装第三方库，只用标准库）：
         cd D:/2026/WB项目/明朝
         python src/extract_auto.py
       只跑前 3 章试水：
         python src/extract_auto.py --limit 3
       强制重抽某几章（即使已抽过）：
         python src/extract_auto.py --force p1-c12 p1-c20

说明：
    - 支持断点续抽：已抽过的章节自动跳过（除非 --force）。
    - 每抽完一章立即写盘，中途中断也不会丢已抽内容。
    - 单个章节调用失败会跳过并继续，最后汇总。
============================================================================
"""

import json, os, sys, time, subprocess, urllib.request, urllib.error

# ============================== 配置（按需修改） ==============================
CONFIG = {
    # OmniRoute 本地网关的 OpenAI 兼容接口
    "API_URL": "http://localhost:20128/v1/chat/completions",
    # 使用的免费模型 id（用 curl http://localhost:20128/v1/models 查真实 id）
    "MODEL": "hy3",
    # 单次请求最大输出 token（五元组一般 2000~3500 token 足够）
    "MAX_TOKENS": 4096,
    # 请求超时（秒）
    "TIMEOUT": 180,
    # 章节之间间隔（秒），避免把免费网关压太狠
    "SLEEP_BETWEEN": 0.5,
}
# ============================================================================

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW  = os.path.join(BASE, "data", "extract_raw.json")
CH   = os.path.join(BASE, "data", "chapters.json")
BATCH= os.path.join(BASE, "data", "_batch.json")
MERGE= os.path.join(BASE, "src", "merge.py")

SYSTEM_PROMPT = (
    "你是一位严谨的中国历史知识抽取助手，专门处理《明朝那些事儿》文本。"
    "你的任务是从给定章节中，抽取结构化'五元组'：角色(characters)、"
    "地点(locations)、事件(events)、关系(relations)、时间(time)。"
    "必须只输出一个 JSON 对象，不要任何解释、不要 markdown 代码块标记、"
    "不要多余文字。JSON 结构如下：\n"
    "{\n"
    '  "characters": [{"name":"姓名","aliases":["别名"],"faction":"势力/阵营","role":"在本章中的身份与作用"}],\n'
    '  "locations": [{"ancient":"古地名/书中称谓","mentioned_as":["书中原话或现代对应地"]}],\n'
    '  "events": [{"name":"事件名","type":"战役/政治斗争/制度/建国/死亡/外交事件/案件/其他","participants":["参与者"],"location":"地点","year":"公元年份如1375，无确切年份填空字符串"}],\n'
    '  "relations": [{"from":"甲","to":"乙","rel":"关系说明"}],\n'
    '  "time":"本章主要年代（如 洪武十三年(1380) 或 至正二十三年(1363)），无则填空"\n'
    "}\n"
    "抽取要求：\n"
    "1. 只抽取本章确实出现、与主线相关的人物/地点/事件，不要编造。\n"
    "2. 人物 faction 用简洁阵营（如 明朝/北元/淮西集团/胡党/汉 等）；role 用一句话说明其在本章作用。\n"
    "3. 地点 ancient 用书中古名；mentioned_as 可写'今XX'或书中原描述。\n"
    "4. 关系 rel 说明二者关系（君臣/父子/政敌/上下级/夫妻/师生/敌对等）。\n"
    "5. 历史人物如朱熹、郑庄公等作为被提及的参照也计入 characters（faction 标其时代）。\n"
    "6. 输出必须是合法 JSON，且不含代码块符号。"
)

DENSE_ADDENDUM = (
    "\n\n【高密度抽取模式】本章在既往抽取中密度偏低。请逐句精读正文，最大化召回：\n"
    "1) 不漏掉任何出场人物，包括仅一笔带过、作为背景被提及的历史人物；\n"
    "2) 不漏掉任何古地名/今地对应，哪怕是过渡性叙述中的地点；\n"
    "3) 不漏掉任何事件（含小规模冲突、任免、制度变动）；\n"
    "4) 尽最大可能补全人物之间、人物与地点之间的关系（君臣/亲属/师生/政敌/上下级/同僚等）；\n"
    "5) 若正文中出现年月或年号，务必填入 year 字段。\n"
    "目标：把本章能被结构化的内容尽可能抽干净，而不是仅抽主线。"
)

def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _is_chapter_key(k):
    """形如 p1-c3 的真正章节 key；排除 部首(p1)、引子、尾声、参考书目等。"""
    parts = k.split("-")
    if len(parts) != 2:
        return False
    head, tail = parts[0], parts[1]
    return (head.startswith("p") and head[1:].isdigit()
            and tail.startswith("c") and tail[1:].isdigit())

def chapter_keys_to_do(chapters, done, force):
    keys = []
    for e in chapters:
        k = e.get("key", "")
        if not _is_chapter_key(k):
            continue
        if k in force:
            keys.append(k)
        elif k not in done:
            keys.append(k)
    return keys

def call_model(chapter_title, body, dense=False):
    user_content = f"章节标题：{chapter_title}\n\n章节正文：\n{body}"
    if dense:
        user_content += DENSE_ADDENDUM
    payload = {
        "model": CONFIG["MODEL"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content}
        ],
        "max_tokens": CONFIG["MAX_TOKENS"],
        "temperature": 0.2,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        CONFIG["API_URL"], data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=CONFIG["TIMEOUT"]) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    content = out["choices"][0]["message"]["content"]
    return content

def extract_json(text):
    """从模型可能夹带的文字中抠出第一个 JSON 对象。"""
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        raise ValueError("未找到 JSON")
    block = text[s:e+1]
    try:
        return json.loads(block)
    except Exception:
        # 退而求其次：去掉 ``` 等
        block = block.replace("```json", "").replace("```", "")
        return json.loads(block)

def run_merge():
    result = subprocess.run([sys.executable, MERGE], cwd=BASE,
                            check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "未知错误").strip()
        raise RuntimeError(f"merge.py 失败：{detail}")
    return result.stdout.strip()

def main():
    args = sys.argv[1:]
    limit = None
    force = set()
    dense = False
    i = 0
    while i < len(args):
        if args[i] == "--limit" and i+1 < len(args):
            limit = int(args[i+1]); i += 2
        elif args[i] == "--force":
            # 后续非 -- 开头的都当 key
            j = i+1
            while j < len(args) and not args[j].startswith("--"):
                force.add(args[j]); j += 1
            i = j
        elif args[i] == "--dense":
            dense = True; i += 1
        else:
            i += 1

    chapters = load_json(CH)
    raw = load_json(RAW)
    done = {e["key"] for e in raw}
    idx = {e["key"]: e for e in chapters}

    todo = chapter_keys_to_do(chapters, done, force)
    if limit:
        todo = todo[:limit]
    print(f"待抽取章节：{len(todo)} 章；已抽取：{len(done)} 章")
    if not todo:
        print("没有需要抽取的章节，退出。")
        return

    collected = []
    ok = 0
    fail = 0
    for n, k in enumerate(todo, 1):
        e = idx.get(k, {})
        title = e.get("chapter") or e.get("title") or k
        body = e.get("body", "")
        if not body.strip():
            print(f"[{n}/{len(todo)}] {k} 无正文，跳过")
            continue
        try:
            content = call_model(title, body)
            obj = extract_json(content)
            rec = {
                "key": k,
                "chapter": title,
                "part": e.get("part") or e.get("part_title") or "",
                "time": obj.get("time", ""),
                "characters": obj.get("characters", []),
                "locations": obj.get("locations", []),
                "events": obj.get("events", []),
                "relations": obj.get("relations", []),
            }
            collected.append(rec)
            ok += 1
            print(f"[{n}/{len(todo)}] {k} ✓ 角色{len(rec['characters'])} 地点{len(rec['locations'])} 事件{len(rec['events'])} 关系{len(rec['relations'])}")
        except Exception as ex:
            fail += 1
            print(f"[{n}/{len(todo)}] {k} ✗ 失败：{ex}")
        # 每章写盘 + 合并，确保中断不丢
        if collected:
            with open(BATCH, "w", encoding="utf-8") as f:
                json.dump(collected, f, ensure_ascii=False, indent=2)
            # 调用 append_batch + merge
            try:
                subprocess.run([sys.executable, os.path.join(BASE,"src","append_batch.py")],
                               cwd=BASE, check=True, capture_output=True, text=True)
                run_merge()
                collected = []  # 已并入，清空临时
                if os.path.exists(BATCH):
                    os.remove(BATCH)
            except Exception as ex:
                print("  [!] 合并失败（稍后手动 merge 也可）：", ex)
        time.sleep(CONFIG["SLEEP_BETWEEN"])

    print(f"\n完成：成功 {ok} 章，失败 {fail} 章。")
    print(f"当前 extract_raw.json 共 {len(load_json(RAW))} 章。")

if __name__ == "__main__":
    main()
