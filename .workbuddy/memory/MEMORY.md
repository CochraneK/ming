# 明朝项目长期记忆（MEMORY.md）

## 项目身份
- **Ming**：本地 `D:\2026\WB项目\明朝`；GitHub `CochraneK/ming`（public）；在线 https://cochranek.github.io/ming/ （根入口，main 分支）。
- **参考实现**：全流程沉淀于用户级 skill `~/.workbuddy/skills/novel-spacetime-knowledge-graph/`（分析《两京十五日》等时空变换类小说时**复制本项目 `src/` 再改**）。项目专属工程细节在 `D:\2026\WB项目\明朝\.workbuddy\skills\ming-report-engineering\`（含全部踩坑速查表），两者勿混用。

## 数据与报告现状（2026-09-04 终态）
- **规模**：章节 156（七部全） / 地点 581（定位 540，92.9%） / 人物 1231 / 事件 1106（未知年份 7）/ 关系 2324 / 在位 17 帝 / 年谱 165 人。部署 HEAD `faf3f82`。
- **视图 12 个**：总览/分布/图谱/地点/地图/人物/事件/关系/时间轴/王朝/年谱/洞察。
- **洞察报告（终版）**：19 节 = 18 学科 + 综合收束；正文 3.1 万字 / 77 小标题；71 条 APA 文献全部 WebSearch 核实；文内引文正则双向核验。学科（最常用叫法定稿）：历史学/心理学/博物馆学/政治学/社会学/人类学/系统科学/经济学/地理学/法学/军事学/叙事学/性别研究/思想史/国际关系/科学史/艺术/传播学。**学科素材已饱和**（徐渭 101 处收、杨应龙 3 处并入），再立新学科=注水；工程→科学史、教育→社会学、宗教→思想史、族群→国际关系均已合并。
- **人物卡**：卡背「书内语录」替代关系行（`data/character_quotes.json` 13 人，全部原文核实），无语录不显示该行；详情弹窗保留关系。
- **地图**：Leaflet 懒加载 + 首屏空闲后台预热（`warmMap()` 预载组件+隐藏地图预热瓦片，点开零等待）；瓦片主源 **Esri**（`makeTiles()` 工厂，tileerror≥6 自动回退 OSM——OSM 在用户网络挂起）；SW 只拦同源（跨域不拦截）；SW `ming-report-v2` + `cache:'no-cache'`（防 GitHub Pages 600s HTTP 缓存拉长更新滞后）；离线 SVG 点图兜底。
- **统计口径**：`data.json` 地点 561（定位 520），报告显示 581/540，差值来自 `event_places.json` 构建时注入（16 coords + aliases），非 bug。

## 关键方法学约定（跨会话有效）
- **写作纪律（用户明确）**：不硬凑字数、言之有物；观点挂文献，新文献必须 WebSearch 核实；书内情节/语录必须先在原书 txt 关键词命中原文（0 命中即弃用）。
- **版权硬约束**：`明朝那些事儿.txt` 与 `data/chapters.json`（全书正文）**绝不发布**（网络免费阅读授权≠可公开再分发，公开仓库分发全文属侵权）；换电脑时这两个文件**私下手动拷贝**（U 盘/私密网盘），README 接续指南已写明步骤。
- **发布**：`.dump/_deploy_index_now.py` 部署 index.html+sw.js+README.md 三文件（Git Database API，`gh` 前必须 `env -u` 清全部代理）；新增数据文件记得加部署 FILES 清单。
- **增量勘误层**（重跑 merge 不丢）：`manual_corrections.json` / `manual_lifespans.json`（卒年-55 占位标估算）/ `manual_persons.json` / `derived_chapter_persons.json` / `event_places.json`（注入须在归一化循环**之前**）/ `geo_annotations.json`（GAZ 元组恒 `(lng,lat,今址,类型)`）。
- **关系约定**：亲属「长辈→晚辈」；端点类型按 人物→地点→政权→派系机构→其他 判定。
- **前端铁律**：CSS 单行模板生成后查 `count('{')-count('}')`；搜索框一律 `bindSearch()`；`load_json()` 只收 Path；改 HTML_TEMPLATE 内 JS 前 grep 游离反引号并用 `node new Function` 校验；agent-browser eval 忌 `?` 与 `[attr]` 选择器。
- **召回探测**：`src/discover_persons.py` 三信号，用 merge 后规范名口径（别名未归一是伪影）；书中人物基本已建卡，不建议为极边角补录。

## 遗留（需人工判断，非阻塞）
- 41 个地点未定位（生僻歧义名，**保持「待核验」不硬填坐标**——巡礼场景错误坐标比缺失更有害）。
- 7 件事件无单一年份（如实保留「年份待考」组）；43.6% 人物无关系（覆盖度非错误）；少数端点（应天/洪都/建文帝）别名未归一。

## 伪遗留（勿再当 bug 排查）
- `reigns` 3 处年份重叠（1457/1567/1620）是史实（夺门之变、两位驾崩同年改元）；`renderPrint` 游离反引号已根治；OmniRoute 重抽已放弃（用户明确），勿再推进。

## 未完成工作清单（换电脑接续指南，详见 README「待办与下一步」）
1. **人物卡语录扩面**（高）：`data/character_quotes.json` 仅 13 人；候选语录先在原书 txt 命中原文再收，规范名入 JSON，重跑 generate。
2. **洞察实体联动**（高）：洞察 19 节文本中的人物/事件/地点做可点击（复用 showCharacter/showEvent/showLocation），反向详情弹窗加"相关洞察"入口。
3. **41 个未定位地点考据**（中）：audit_final.py 出清单，确认后进 enrich_geo.py GAZ 或 event_places.json。
4. **7 件未知年份事件考证**（中）：查实写入 manual_corrections.json 的 event_years。
5. **数据清洁**（低）：端点别名归一、mentioned_as 串味、张瑾→张軏方向；43.6% 无关系人物不建议强补。
完成后跑「交付检查」四步 + `.dump/_deploy_index_now.py` 部署 + `.dump/_sync_docs.py` 同步文档。

## 历史明细
详见 `.workbuddy/memory/YYYY-MM-DD.md` 日志（2026-08-24 起逐日）与 `2026-08-28.md`（第十一轮交叉审计：4 P0 + 15 史实勘误 + 6 人物合并 + 17 关系归一）。
