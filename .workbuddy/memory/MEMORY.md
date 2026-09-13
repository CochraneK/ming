# 明朝项目长期记忆（MEMORY.md）

## 项目身份
- **Ming**：本地 `D:\2026\WB项目\明朝`；GitHub `CochraneK/ming`（public）；在线 https://cochranek.github.io/ming/ （根入口，main 分支）。
- **参考实现**：全流程沉淀于用户级 skill `~/.workbuddy/skills/novel-spacetime-knowledge-graph/`（分析《两京十五日》等时空变换类小说时**复制本项目 `src/` 再改**）。项目专属工程细节在 `D:\2026\WB项目\明朝\.workbuddy\skills\ming-report-engineering\`（含全部踩坑速查表），两者勿混用。

## 数据与报告现状（2026-09-13）
- **规模**：章节 156 / 地点 581（定位 540，92.9%）/ 人物 1231 / 事件 1106（未知年份 7）/ 关系 2324 / 在位 17 帝 / 年谱 165 人。
- **视图 12 个**：总览/分布/图谱/地点/地图/人物/事件/关系/时间轴/王朝/年谱/洞察。
- **构建（Phase 4 起）**：`python src/build.py`（`--scope full|p1..p7`、`--target standalone|web`、`--check`、`--json`）全量 **约 2 秒**。前端模板/CSS/JS 在 `web/`，**改前端只动 `web/`**，不要在 Python 里再写一份；单文件由 `compose_document()` 唯一注入。旧入口 `generate_report.py` 仍可跑（等价）。
- **校验三层**：`src/build.py --check`（`src/validators.py` 结构不变量，ERROR 退出码 2）→ `src/audit_final.py`（深审，ERROR 退出码 1）→ `tests/run_tests.py`（28 例，纯标准库，也兼容 pytest）。前端真机验真用 `.dump/_browser_check.py`（Chrome `--dump-dom` 跑 7 场景，deep link/高亮/地图）。
- **CI**：`.github/workflows/ci.yml`（版权巡检→语法→单测→构建门禁→深审→构建产物+无头自检），**实测 green**；不需要 `data/chapters.json`（标题取自 `extract_raw.json`）。
- **人物关系图口径（方案 A）**：节点只允许人物表内实体；**686 人 / 1403 边 / 孤立 545（44.3%）/ 排除 72 条含非人物端点的关系**（东林党/东厂/后金/北京等 47 个非人物端点不再入图，但仍保留在关系卡与详情）。
- **关系范围**：`build_scope` 的 `relation_scope`：全书=all，分部(p1~p7)=**induced**（两端都在本范围内），payload 带 `relationScope`，关系视图顶部标注。判据是「两端人物在不在范围」，**不是**「关系 source 章节在不在范围」（source 可为 curated/推导）。
- **统一 ID（Phase 3）**：`entity_id()` → `person:朱由检`；`relation_id()` = `relation:<sha1[:12]>`（内容寻址，重跑稳定）；payload 带 `model:{schemaVersion:2,entityTypes,idIndex}`。
- **共享核心**：`src/core/year_parser.py`（year_bounds；非数字年份→None→页面「年份待考」）、`src/core/geo.py`（is_valid_lat/lng、has_coords；**禁止 `if not lat`**，0 是合法值）。生产与审计必须共用，勿再各写一份。
- **审计**：`python src/audit_final.py`（`--quick` 跳过分部）= 直接 import `generate_report` 审 **build_scope("full") 最终模型**；分级 INFO/WARNING/ERROR，**有 ERROR 返回 1**。当前 INFO 17 / WARNING 2 / ERROR 0。
- **洞察报告**：19 节 = 18 学科 + 综合；3.1 万字 / 71 条 APA（全部 WebSearch 核实）。学科素材已饱和，勿再立新学科。
- **人物卡**：卡背「书内语录」替代关系行（`data/character_quotes.json` 13 人，全部原文核实）；搜索命中姓名**或别名**（`aliasIndex` 444 条 + `matchesQuery()`），仍无命中才显示空态。
- **地图**：Leaflet 懒加载 + 首屏空闲后台预热（用户明确要求，勿改成仅 hover 加载），并叠加 hover/touchstart 即时预热；瓦片主源 Esri + `tileerror≥6` 回退 OSM；SW 只拦同源、`cache:'no-cache'`、后台更新 `event.waitUntil` 保活；CACHE `ming-report-v5`。
- **URL deep link（Phase 6）**：`#view=…&person=…&detail=1&event=…&place=…&era=…&map=…&q=…`；`person=` 支持别名，会切到人物视图 + 预填搜索 + 滚动闪烁定位；打开详情把实体写回地址栏（可分享同一张卡）；搜索命中高亮 `mark.hl`；tabs 有 `role=tablist/tab/tabpanel` + 方向键。

## 关键方法学约定（跨会话有效）
- **写作纪律（用户明确）**：不硬凑字数、言之有物；观点挂文献，新文献必须 WebSearch 核实；书内情节/语录必须先在原书 txt 关键词命中原文（0 命中即弃用）。
- **版权硬约束**：`明朝那些事儿.txt` 与 `data/chapters.json` **绝不发布**；换电脑私下手动拷贝，README 接续指南已写明步骤与不拷的后果。
  - **2026-09-13 事故**：`data/chapters.json`（4.5MB 全文本）其实早在 2026-09-04 就混进了公开仓库（`.gitignore` 只挡 `git add`，挡不住 API 上传）。已从 main 移除（commit `470918be`），但**历史 commit `7190215d` 仍可访问该 blob**——彻底清除需重写历史（孤儿 commit + force refs），**待用户决定**。
  - 部署/同步后必跑合规巡检：`gh api "/repos/CochraneK/ming/git/trees/main?recursive=1" --jq '.tree[]|select(.type=="blob")|.path' | grep -Ei 'chapters\.json|明朝那些事儿'`，期望无输出。
- **发布**：`.dump/_deploy_index_now.py`（index.html+sw.js+README.md，Git Database API，3 次重试，`gh` 前内部清代理，消息可 `MING_DEPLOY_MESSAGE=` 覆盖）；`.dump/_sync_docs.py` 全量清单（源码+数据+`web/`+`tests/`+`.github/`+`.dump/`脚本+文档，消息可 `MING_SYNC_MESSAGE=` 覆盖）；**新增文件必须补 FILES 清单**，否则 CI 会因缺文件报错。差异检查 `.dump/_diff_remote.py`（期望「过时 0」）。
- **前端验真**：`.dump/_browser_check.py`（Chrome `--dump-dom`，7 场景）。断言**必须正则匹配真实标签**——产物内联了 JS，裸串 `'flash' in dom` 会假通过；临时高亮类用短 `budget` 抓。
- **增量勘误层**（重跑 merge 不丢）：`manual_corrections.json` / `manual_lifespans.json` / `manual_persons.json` / `derived_chapter_persons.json` / `event_places.json`（注入须在归一化循环**之前**）/ `geo_annotations.json`（条=dict，含 ancient/modern_address/lng/lat/…）。
- **关系约定**：亲属「长辈→晚辈」；端点类型按 人物→地点→政权→派系机构→其他 判定。
- **前端铁律**：CSS 单行模板查 `count('{')-count('}')`；搜索框一律 `bindSearch()`；`load_json()` 只收 Path；改 JS 后 `node --check web/js/app.js`；`Path.as_uri()` 需绝对路径；`.dump/` 新脚本记得进同步清单。
- **环境**：Bash 的 PATH 可能被裁（`ls`/`tail`/`dirname`/`env`/`rm`/`agent-browser` 消失）→ 外部程序一律绝对路径（python 3.13.12 / node 22.22.2-3 / Chrome），列目录用 `os.listdir`，删目录用 `shutil.rmtree`。编辑工具偶发「报成功但没落盘」→ 改完 grep 复核。
- **召回探测**：`src/discover_persons.py` 三信号，用 merge 后规范名口径（别名未归一是伪影）。

## 未完成工作清单（详见 README「待办与下一步」）
1. **人物卡语录扩面**（高）：13/1231；候选先在原书 txt 命中原文再收，规范名入 JSON，重跑 generate。
2. **洞察实体联动**（高）：19 节正文的人物/事件/地点可点击 + 反向「相关洞察」入口。
3. **41 个未定位地点考据**（中）：确认后进 enrich_geo.py GAZ 或 event_places.json。
4. **7 件未知年份事件考证**（中）：写入 manual_corrections.json 的 event_years。
5. **同名异地拆分**（中，新）：`延安府` = 陕西延安 + 朝鲜黄海南道延安（万历援朝战场），地点表目前只剩陕西那条；审计 R-GEO-03 持续提醒。
6. **数据清洁**（低）：端点别名归一、mentioned_as 串味、张瑾→张軏方向；44.3% 无人物间关系者不建议强补。
7. **已决策（勿再当冲突项）**：别名搜索与地图预热**两者都要**，均已实现且不冲突（2026-09-13 用户明确）。
8. **Phase 3~6 已完成**（统一 ID / web 拆分+build.py / validators+tests+CI / deep link+高亮+无障碍）；仅剩 **Phase 6 的「人物图/实体图双模式」**未做——需先把非人物实体补进节点层，与方案 A（节点只允许人物）冲突，**需先定口径**；移动端详情抽屉判定为不必做（现有 dialog 已自适应）。
9. **待决（重要）**：是否重写 git 历史彻底清除 `data/chapters.json` 的旧 blob（历史 commit `7190215d` 仍可直达）。

## 伪遗留（勿再当 bug 排查）
- `reigns` 3 处年份重叠（1457/1567/1620）是史实（夺门之变、驾崩同年改元）；审计 R-REIGN-01 只报 INFO。
- geo 标注 93 条「不在地点表」其实都是旧称（应天→南京、濠州→凤阳、平江→苏州），已由 `mentioned_as` 别名合并，审计列 INFO；判定 stale 必须**先查原名再查别名**。
- `data.json` 地点 561 vs 报告 581 = `event_places.json` 构建时注入，非 bug。
- `renderPrint` 游离反引号已根治；OmniRoute 重抽已放弃（用户明确）。

## 历史明细
详见 `.workbuddy/memory/YYYY-MM-DD.md`（逐日）；重点：`2026-09-13.md`（第一轮：重构 Phase 1+2 落地与勘验；第二轮：Phase 3~6 全量落地 + CI green + 部署终态 e1cbd30/2625e53/e6e1a5d）、`2026-08-28.md`（第十一轮交叉审计）、`2026-09-04.md`（洞察终版/语录/地图）。
