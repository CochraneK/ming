# 明朝项目长期记忆（MEMORY.md）

## 项目身份
- **Ming**：本地 `D:\2026\WB项目\明朝`；GitHub `CochraneK/ming`（public）；在线 https://cochranek.github.io/ming/ （根入口，main 分支）。
- **参考实现**：全流程沉淀于用户级 skill `~/.workbuddy/skills/novel-spacetime-knowledge-graph/`（分析《两京十五日》等时空变换类小说时**复制本项目 `src/` 再改**）。项目专属工程细节在 `D:\2026\WB项目\明朝\.workbuddy\skills\ming-report-engineering\`（含全部踩坑速查表），两者勿混用。

## 数据与报告现状（2026-09-13）
- **规模**：章节 156 / 地点 581（定位 540，92.9%）/ 人物 1231 / 事件 1106（未知年份 7）/ 关系 2324 / 在位 17 帝 / 年谱 165 人。
- **视图 12 个**：总览/分布/图谱/地点/地图/人物/事件/关系/时间轴/王朝/年谱/洞察。
- **构建**：`python src/generate_report.py` 全量 **约 2 秒**（2026-09-13 移除 Python 端 800 轮 numpy 力导布局，109.7s→2.3s；力模拟改由浏览器 `fullStep()` 承担，Python 只给确定性初始坐标）。
- **人物关系图口径（方案 A）**：节点只允许人物表内实体；**686 人 / 1403 边 / 孤立 545（44.3%）/ 排除 72 条含非人物端点的关系**（东林党/东厂/后金/北京等 47 个非人物端点不再入图，但仍保留在关系卡与详情）。
- **关系范围**：`build_scope` 的 `relation_scope`：全书=all，分部(p1~p7)=**induced**（两端都在本范围内），payload 带 `relationScope`，关系视图顶部标注。
- **共享核心（新）**：`src/core/year_parser.py`（year_bounds；非数字年份→None→页面「年份待考」）、`src/core/geo.py`（is_valid_lat/lng、has_coords；**禁止 `if not lat`**，0 是合法值）。生产与审计必须共用，勿再各写一份。
- **审计**：`python src/audit_final.py`（`--quick` 跳过分部）= 直接 import `generate_report` 审 **build_scope("full") 最终模型**；分级 INFO/WARNING/ERROR，**有 ERROR 返回 1**。当前 INFO 16 / WARNING 2 / ERROR 0。
- **洞察报告**：19 节 = 18 学科 + 综合；3.1 万字 / 71 条 APA（全部 WebSearch 核实）。学科素材已饱和，勿再立新学科。
- **人物卡**：卡背「书内语录」替代关系行（`data/character_quotes.json` 13 人，全部原文核实）；**搜索只匹配姓名字段，无匹配显示空态**（用户明确）。
- **地图**：Leaflet 懒加载 + 首屏空闲后台预热（用户明确要求，勿改成 hover 加载）；瓦片主源 Esri + `tileerror≥6` 回退 OSM；SW 只拦同源、`cache:'no-cache'`、后台更新 `event.waitUntil` 保活；CACHE `ming-report-v4`。

## 关键方法学约定（跨会话有效）
- **写作纪律（用户明确）**：不硬凑字数、言之有物；观点挂文献，新文献必须 WebSearch 核实；书内情节/语录必须先在原书 txt 关键词命中原文（0 命中即弃用）。
- **版权硬约束**：`明朝那些事儿.txt` 与 `data/chapters.json` **绝不发布**；换电脑私下手动拷贝，README 接续指南已写明步骤与不拷的后果。
- **发布**：`.dump/_deploy_index_now.py`（index.html+sw.js+README.md，Git Database API，`gh` 前 `env -u` 清代理）；新增数据文件记得加 FILES 清单。差异检查：`.dump/_sync_docs.py` + blob sha 全量比对法（见 skill 节）。
- **增量勘误层**（重跑 merge 不丢）：`manual_corrections.json` / `manual_lifespans.json` / `manual_persons.json` / `derived_chapter_persons.json` / `event_places.json`（注入须在归一化循环**之前**）/ `geo_annotations.json`（条=dict，含 ancient/modern_address/lng/lat/…）。
- **关系约定**：亲属「长辈→晚辈」；端点类型按 人物→地点→政权→派系机构→其他 判定。
- **前端铁律**：CSS 单行模板查 `count('{')-count('}')`；搜索框一律 `bindSearch()`；`load_json()` 只收 Path；改内联 JS 前 grep 游离反引号 + `node --check`；agent-browser eval 忌 `?`/`[attr]`。
- **环境**：Bash 的 PATH 可能被裁（`ls`/`tail`/`dirname`/`agent-browser` 消失）→ 外部程序一律绝对路径（python 3.13.12 / node 22.22.2-3），列目录用 `os.listdir`。编辑工具偶发「报成功但没落盘」→ 改完 grep 复核。
- **召回探测**：`src/discover_persons.py` 三信号，用 merge 后规范名口径（别名未归一是伪影）。

## 未完成工作清单（详见 README「待办与下一步」）
1. **人物卡语录扩面**（高）：13/1231；候选先在原书 txt 命中原文再收，规范名入 JSON，重跑 generate。
2. **洞察实体联动**（高）：19 节正文的人物/事件/地点可点击 + 反向「相关洞察」入口。
3. **41 个未定位地点考据**（中）：确认后进 enrich_geo.py GAZ 或 event_places.json。
4. **7 件未知年份事件考证**（中）：写入 manual_corrections.json 的 event_years。
5. **同名异地拆分**（中，新）：`延安府` = 陕西延安 + 朝鲜黄海南道延安（万历援朝战场），地点表目前只剩陕西那条；审计 R-GEO-03 持续提醒。
6. **数据清洁**（低）：端点别名归一、mentioned_as 串味、张瑾→张軏方向；44.3% 无人物间关系者不建议强补。
7. **待决策冲突**：① 别名搜索（方案 P2-01）vs 现存「只搜姓名字段」；② 地图不预载（方案 P2-06）vs 现存后台预热。
8. **待排期 Phase 3~6**：canonical id / entity_type / 拆分 1567 行 generate_report（HTML·CSS·JS 外置 + build.py）/ pytest+GitHub Actions / URL deep link。

## 伪遗留（勿再当 bug 排查）
- `reigns` 3 处年份重叠（1457/1567/1620）是史实（夺门之变、驾崩同年改元）；审计 R-REIGN-01 只报 INFO。
- geo 标注 93 条「不在地点表」其实都是旧称（应天→南京、濠州→凤阳、平江→苏州），已由 `mentioned_as` 别名合并，审计列 INFO；判定 stale 必须**先查原名再查别名**。
- `data.json` 地点 561 vs 报告 581 = `event_places.json` 构建时注入，非 bug。
- `renderPrint` 游离反引号已根治；OmniRoute 重抽已放弃（用户明确）。

## 历史明细
详见 `.workbuddy/memory/YYYY-MM-DD.md`（逐日）；重点：`2026-09-13.md`（重构 Phase 1+2 落地与勘验）、`2026-08-28.md`（第十一轮交叉审计）、`2026-09-04.md`（洞察终版/语录/地图）。
