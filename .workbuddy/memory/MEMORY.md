# 明朝项目长期记忆（MEMORY.md）

## 项目身份
- **Ming**：本地 `D:\2026\WB项目\明朝`；GitHub `CochraneK/ming`（public）；在线 https://cochranek.github.io/ming/ （根入口，main 分支）。
- **参考实现**：全流程沉淀于用户级 skill `~/.workbuddy/skills/novel-spacetime-knowledge-graph/`（分析《两京十五日》等时空变换类小说时**复制本项目 `src/` 再改**）。项目专属工程细节在 `D:\2026\WB项目\明朝\.workbuddy\skills\ming-report-engineering\`（v3.2.0，含全部踩坑速查表），两者勿混用。

## 数据与报告现状（2026-09-13 第六轮终态）
- **规模**：章节 156 / 地点 583（定位 553，**94.9%**）/ 人物 1231 / 事件 1106（未知年份 **2**）/ 关系 2324 / 在位 17 帝 / 年谱 165 人。`data.json` 口径地点 563。
- **视图 12 个**：总览/分布/图谱/地点/地图/人物/事件/关系/时间轴/王朝/年谱/洞察。
- **构建（Phase 4 起）**：`python src/build.py`（`--scope full|p1..p7`、`--target standalone|web`、`--check`、`--json`）全量 **约 2 秒**，单文件 **5.13 MB**（gzip 0.83 MB）。前端模板/CSS/JS 在 `web/`，**改前端只动 `web/`**；单文件由 `compose_document()` 唯一注入。
- **校验三层**：`src/build.py --check`（`src/validators.py` **12 组**结构不变量，ERROR→退出码 2）→ `src/audit_final.py`（深审，ERROR→1；当前 INFO 17/WARNING 2/ERROR 0）→ `tests/run_tests.py`（**45 例**，纯标准库，兼容 pytest）。前端真机验真 `.dump/_browser_check.py`（Chrome `--dump-dom`，**11 场景 + 启动守卫**）。
- **CI**：`.github/workflows/ci.yml`（版权巡检→语法→单测→构建门禁→深审→产物+无头自检），实测 green；不需要 `data/chapters.json`。
- **人物关系图口径（方案 A）**：节点只允许人物表内实体；**686 人 / 1403 边 / 孤立 545（44.3%）/ 排除 72 条含非人物端点的关系**。
- **关系图双模式（Phase 6）**：`activeGraph()` 是模式分发唯一入口；`net=full` 人物图 686/1403，`net=entity` 实体图 **741 实体 / 1467 条**（人物 694 + 机构 12 + 其他 16 + 地点 15 + 政权 4）。**契约：人物图节点/边 ⊆ 实体图（1403 ⊆ 1467）**，有测试守。数字绝不能互相串（实体图不能说「N 名人物」）。
- **势力结构化（P2-03）**：`src/core/faction_profile.py` 构建期一次性解析 `characters[].faction` → `profile{raw,label,regime,dynasty,period,factions,orgs,categories,office,origin,jinshi_year,note}`。覆盖率：政权 1161/1231（94.3%）、官职 426、身份类别 320、派系 109、籍贯 26、科举 16，未归类 16。前端 `cleanCardFields()` **优先读 profile**、正则只兜底。**解析必须用完整 role 原串**（`item["_roleRaw"]`，`clean_role()` 会截断导致失真）。
- **关系范围**：全书=all，分部(p1~p7)=**induced**（两端都在本范围内），payload 带 `relationScope`。判据是「两端人物在不在范围」，**不是**「关系 source 章节在不在范围」。
- **统一 ID（Phase 3）**：`entity_id()` → `person:朱由检`；`relation_id()` = `relation:<sha1[:12]>`；payload 带 `model:{schemaVersion:3,entityTypes,idIndex}` 与 `relationGraphEntities`。
- **共享核心**：`src/core/{year_parser,geo,faction_profile,graph_layout}.py`。生产与审计必须共用，勿再各写一份。`geo` **禁止 `if not lat`**（0 是合法值）。
- **洞察报告**：19 节 = 18 学科 + 综合；3.1 万字 / 71 条 APA（全部 WebSearch 核实）。学科素材已饱和，勿再立新学科。
- **人物卡**：卡背「书内语录」替代关系行（13 人，全部原文核实）；搜索命中姓名**或别名**（`aliasIndex` 444 + `matchesQuery()`），无命中才显示空态。
- **地图**：Leaflet 懒加载 + 首屏空闲后台预热（用户明确要求，勿改成仅 hover）+ hover/touchstart 即时预热；瓦片主源 Esri + `tileerror≥6` 回退 OSM；SW 只拦同源、`cache:'no-cache'`、后台更新 `event.waitUntil` 保活；**CACHE `ming-report-v6`**。
- **统一错误 UI（P3-03）**：`failBar()/dismissFail()/reportRuntimeError()` 底部提示条，5 类接入（数据缺失 / 主脚本未初始化 / 渲染异常 / Leaflet 失败 / 瓦片全失败）；**启动守卫是独立 `<script>` 且排在主脚本之前**（主脚本解析失败时它仍能跑）；`app.js` 内**禁止静默空 catch**（有测试断言）。
- **URL deep link（Phase 6）**：`#view=…&person=…&detail=1&event=…&place=…&era=…&map=…&q=…&net=…&from=…&to=…`；`person=` 支持别名 + 滚动闪烁定位；打开详情写回地址栏；`mark.hl` 高亮；tabs `role=tablist/tab/tabpanel` + 方向键；三张纯图形（canvas/热力图/网络 SVG）均有 `role="img"` + 描述性 `aria-label`。

## 关键方法学约定（跨会话有效）
- **写作纪律（用户明确）**：不硬凑字数、言之有物；观点挂文献，新文献必须 WebSearch 核实；书内情节/语录必须先在原书 txt 命中原文（0 命中即弃用）。
- **版权硬约束**：`明朝那些事儿.txt` 与 `data/chapters.json` **绝不发布**；换电脑私下手动拷贝。
  - **2026-09-13 事故**：`data/chapters.json` 早在 2026-09-04 混进公开仓库（`.gitignore` 只挡 `git add`，挡不住 API 上传）。已从 main 移除；历史 commit `7190215d` 仍可访问该 blob，**用户明确「不用管了」，放弃重写历史**。
  - 部署/同步后必跑合规巡检：`gh api "/repos/CochraneK/ming/git/trees/main?recursive=1" --jq '.tree[]|select(.type=="blob")|.path' | grep -Ei 'chapters\.json|明朝那些事儿'`，期望无输出。
- **发布**：`.dump/_deploy_index_now.py`（index.html+sw.js+README.md，Git Database API，3 次重试，内部清代理，`MING_DEPLOY_MESSAGE=` 可覆盖）；`.dump/_sync_docs.py` 全量清单（`MING_SYNC_MESSAGE=` 可覆盖）；**新增文件必须补 FILES 清单**（本轮已补 `src/core/faction_profile.py`、`src/core/graph_layout.py`、`report/Ming_重构验收清单.md`），否则 CI 报缺文件。差异检查 `.dump/_diff_remote.py`（期望「过时 0」）。
- **前端验真**：`.dump/_browser_check.py`。断言**必须正则匹配渲染标签**（产物内联 JS，裸串会假通过）；**`--dump-dom` 把布尔属性序列化成 `key=""`**；属性顺序不可假设（`id="x"[^>]*value="…"`）；要区分「渲染出来」与「源码里写着」用场景的 `scoped`（锚定元素 + 限定窗口）；兜底路径用注入语法错误的副本验证。
- **增量勘误层**（重跑 merge 不丢）：`manual_corrections.json` / `manual_lifespans.json` / `manual_persons.json` / `derived_chapter_persons.json` / `event_places.json`（注入须在归一化循环**之前**）/ `geo_annotations.json` / `manual_event_years.json`。
- **同名异地两级拆分（第六轮新增，`merge.py`）**：`location_splits`（键=`原始地点串`，如 `延安府/清州` → `延安府（朝鲜）`）+ `location_splits_by_chapter`（键=`章节key`，如 `p5-c17` → 龙山（朝鲜））。**判据必须落在「章节」或「原始串」上**——两处同名地点的片段名本来就相同，只按片段名拆不开。**两处 splits 必须在「地点归一化循环之前」加载**（其余勘误块仍在关系构建前应用），归一化后才走 `location_fixes`/geo 坐标（坐标须按新名书写）。
- **关系约定**：亲属「长辈→晚辈」；端点类型按 人物→地点→政权→派系机构→其他 判定。
- **前端铁律**：CSS 单行模板查 `count('{')-count('}')`；搜索框一律 `bindSearch()`；`load_json()` 只收 Path；改 JS 后 `node --check web/js/app.js`；`Path.as_uri()` 需绝对路径；`.dump/` 新脚本记得进同步清单。
- **体积铁律**：骨架（含注释）里**绝不书写数据占位符名**——字符串替换会把整份 payload 注入两遍（实测 5.6MB→11.4MB）；改注入相关代码后跑 `doc.count('"scopeLabel"')==1` 自检。
- **环境**：Bash 的 PATH 可能被裁（`ls`/`tail`/`dirname`/`env`/`rm`/`head`/`grep` 消失）→ 外部程序一律绝对路径（python 3.13.12 / node 22.22.2-3 / Chrome），列目录用 `os.listdir`，管线过滤改用 Python。编辑工具偶发「报成功但没落盘」→ 改完复核。
- **召回探测**：`src/discover_persons.py` 三信号，用 merge 后规范名口径（别名未归一是伪影）。

## 方案落地终态（`report/Ming_重构验收清单.md`，2026-09-13 终版）
- **25 个条目：✅23 / 🟡1（P2-02：`from`/`to` 保留显示名是有意决策）/ ⏸1（P2-09：`.workbuddy/memory` 有意入库做接续指南）**。方案项**已全部闭环，不要再当 TODO 找**；唯一"不必做"是移动端详情抽屉（现有 dialog 已自适应）。
- 量化：构建 109.7s→约 2.7s；单文件 11.39MB→**5.13MB（−55%）**；测试 0→45；validators 10→12 组；浏览器自检 0→11 场景。
- **本轮修掉的真实缺陷**（都是自查发现，非用户报告）：① 骨架注释里的占位符导致 payload 注入两遍；② `const activeGraph` 自递归（栈溢出打挂图谱）；③ `#fullNet` 显示表达式漏 `entity` 模式（深链进来空白/两块同显）；④ `_extract_origin` 过严漏掉 2~4 字府县籍贯（22→26）。

## 未完成工作清单（内容层，非工程层）
1. **人物卡语录扩面**（高）：现有 13/1231（`data/character_quotes.json`，dict 首键 `_comment`）。**候选池已探测**：正文中「姓名+言语动词（说/道/曰/答/问/骂/叹/笑/哭/怒/喊…）+ 引号」命中 **77 人**，扣掉已入库 13 → **71 个候选**（含少量误报，如单字「高」「乃公」，实收前须逐条原文核实）。前批可用：罗复仁、常遇春、朱棣、蓝玉、朱祁镇、也先、张辅、石亨、朱允炆、黄子澄、铁铉、解缙、张居正、杨士奇、杨荣、冯保、魏忠贤、徐有贞、杨善、曹吉祥、张軏、王文、李贤、曹钦、韩雍、朱祐樘、怀恩、杨廷和、李东阳、江彬、张钦、朱宸濠、孙燧、许逵、蒋瑶、朱厚熜…。**收编纪律**：语录必须先在原书 txt 命中原文，规范名入 JSON。
2. **洞察实体联动**（高）：19 节正文的人物/事件/地点可点击 + 反向「相关洞察」入口。
3. **未定位地点 30 个**（原 41，中）：多为漠北蒙古草原地名（15 世纪定位困难且有争议），按「宁可留空不可猜错」纪律不动；`车迟国` 已标 `status:"非实地"`。剩余可考者进 `geo_annotations.json` 或 `event_places.json`。
4. **未知年份事件 2 件**（原 7，中）：仅余「严世蕃论天下三人」（纯对话场景）与「朱棣生母碽妃之谜」（后世身世考据），均无可靠纪年。补年机制：空 `year` 走 `manual_event_years.json`（只回填），非空但不可解析（如「万历末年」）走 `manual_corrections.event_years`（覆盖式）。
5. **同名异地拆分 ✅ 已落地**（第六轮）：`延安府`（陕西延安 109.49/36.59 vs 朝鲜黄海道延安 126.08/37.92）、`龙山`（浙江慈溪 121.45/30.05 vs 朝鲜汉城龙山 126.96/37.53）两组已分离，各自只挂对应章节。机制见上「同名异地两级拆分」。审计 R-GEO-03 后续仍可能提示其他候选取对。
6. **数据清洁**（低）：端点别名归一、mentioned_as 串味、张瑾→张軏方向；44.3% 无人物间关系者不建议强补。
7. **有意不做的冗余压缩**（别当 TODO）：`relations[].endpointKind`、`sourceId/targetId` 可推导（约 3%）；`characters[].relations` **不是** `DATA.relations` 的纯投影（实测 168/1231 人卡上更少，是设计上的子集），**不能改客户端推导**。

## 伪遗留（勿再当 bug 排查）
- `data/chapters_index.json`（**线上独有**，40,388 B，仅分部/章标题/键名，无正文）是自 2026-08-26 起**有意发布**的脱敏目录替代品；`_diff_remote.py` 已白名单放行，diff 报「仅线上」不算问题。合规巡检的过滤串是 `chapters\.json|明朝那些事儿`，**故意不匹配**它。
- `reigns` 3 处年份重叠（1457/1567/1620）是史实；审计 R-REIGN-01 只报 INFO。
- geo 标注 93 条「不在地点表」其实都是旧称（应天→南京、濠州→凤阳、平江→苏州），已由 `mentioned_as` 合并；判定 stale 必须**先查原名再查别名**。
- `data.json` 地点 563 vs 报告 583 = `event_places.json` 构建时注入，非 bug（第四轮 561/581 同理）。
- `renderPrint` 游离反引号已根治；OmniRoute 重抽已放弃（用户明确）。
- 「明朝·福建进士」这类无年份的进士表述，`jinshi_year` 为空是**正确**的（宁可留空不可猜错）。

## 历史明细
详见 `.workbuddy/memory/YYYY-MM-DD.md`（逐日）；重点：`2026-09-13.md`（一~六轮：Phase 1+2 落地 → Phase 3~6 全量 + CI green → 方案逐条验收 → 剩余 5 项全部补齐 + 体积 −55% → CI/线上一致性复核 → 同名异地两级拆分 + 事件补年 + 地点考据）、`2026-08-28.md`（第十一轮交叉审计）、`2026-09-04.md`（洞察终版/语录/地图）。
