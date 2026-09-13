# 《明朝那些事儿》报告工程 · 全面重构方案 验收清单

- 方案来源：`report/Ming_全面重构方案.txt`（1077 行 / 22 章 / 25 个条目）
- 首轮验收：2026-09-13（结论 ✅17 / 🟡6 / ❌1 / ⏸1）
- 二轮补齐：2026-09-13 同日完成剩余 5 项，**本文件为终版**
- 验收方式：逐条对照方案原文核对代码与产物，并实跑三层校验 + 无头浏览器自检
- 终版结论：**25 条中 ✅ 完成 23 条 / 🟡 部分完成 1 条 / ⏸ 有意不做 1 条**

---

## 一、P1 级正确性修复（12/12 完成）

| 条目 | 状态 | 落地证据 |
| --- | --- | --- |
| P1-01 关系图混入非人物实体 | ✅ | 采用方案 A：节点只允许人物表内实体。人物图 **686 人 / 1403 边**，**排除 72 条含非人物端点的关系**。二轮另加**实体图**保留全部端点（741 实体 / 1467 条），口径由页面文案与校验分列 |
| P1-02 孤立人物统计错误 | ✅ | 严格集合关系：**686 连接 + 545 孤立 = 1231 人物**（孤立占 44.3%）。`tests` 有 `test_graph_isolated_arithmetic` 守住恒等式 |
| P1-03 Python 端力导向是瓶颈 | ✅ | Python 不再跑力导（原 ~800 轮 × O(n²)）。改为**确定性初始布局**：按势力分扇区 + 扇区内螺旋，O(n)、无随机、无 numpy。构建 **109.7s → 2.68s（约 41×）** |
| P1-04 NumPy 可选依赖静默损坏 | ✅ | 力导移除后 numpy 依赖同步移除；`import numpy` 已不存在，不再存在"构建成功但 links=0"的静默退化路径 |
| P1-05 审计与产品数据语义不一致 | ✅ | 新建共享核心 `src/core/year_parser.py`（`year_bounds`）。生产与审计共用：「万历末年」两端都判为未知年份，**未知年份 7 件在审计与页面完全一致** |
| P1-06 审计未覆盖最终数据 | ✅ | `src/audit_final.py` 直接 `import generate_report` 审 `build_scope("full")` 的**最终模型**，不再读中间文件近似版本。地点 **581 = 581** 对齐 |
| P1-07 审计存在死代码/无效逻辑 | ✅ | 死代码清除；**26 条规则全部带 `rule_id`（R-xxx-00）+ severity + message + affected records**；ERROR 级 `sys.exit(1)` |
| P1-08 经纬度空值判断不严谨 | ✅ | 新建 `src/core/geo.py`：`is_valid_lat` / `is_valid_lng` / `has_coords` / `coord_problem`，禁止 `if not lat`（0 是合法值）。`test_geo_zero_is_valid` 守住 |
| P1-09 审计无论发现什么 exit 0 | ✅ | 定义 INFO / WARNING / ERROR 三级；有 ERROR → **退出码 1**（build `--check` 结构不变量 ERROR → **退出码 2**）。CI 依次跑 构建门禁 → 单测 → 深审，任一失败即红 |
| P1-10 `extract_auto.py --dense` 无效 | ✅ | 已修为 `call_model(title, body, dense=dense)`，参数真正透传 |
| P1-11 分部 scope 关系串范围 | ✅ | 全书 = `all`，分部(p1~p7) = **`induced`（两端人物都在本范围内）**；payload 带 `relationScope`，关系视图顶部有范围标注 |
| P1-12 SW stale-while-revalidate 不可靠 | ✅ | 后台更新用 `event.waitUntil(network.catch(...))` 保活；`CACHE='ming-report-v6'`（第六轮内容勘误起 bump 至 `v7`），`activate` 时清理所有同前缀旧缓存 |

## 二、P2 级重要改进（8 完成 / 1 部分 / 1 有意不做）

| 条目 | 状态 | 落地证据 |
| --- | --- | --- |
| P2-01 人物搜索支持 aliases | ✅ | 生成 **`aliasIndex` 444 条**（崇祯→朱由检、王阳明→王守仁）；全视图共用 `matchesQuery()`，命中姓名**或别名**，高亮 `mark.hl` |
| P2-02 统一实体解析系统 | 🟡 | 已建统一 ID：`entity_id()` → `person:朱由检`；`relation_id()` = sha1 内容寻址（重跑稳定）；payload 带 `model:{schemaVersion:3, entityTypes, idIndex}`；关系带 `sourceId`/`targetId`/`endpointKind`。**有意保留**：`from`/`to` 仍是显示名——全站以姓名为主键（人物卡查找、deep link、力导图节点 key 都按姓名），改成纯 id 需要改动整条前端链路而不带来可见收益，故判定「id 与显示名并存」即为终态 |
| P2-03 faction 字段规范化 | ✅ | 二轮落地 `src/core/faction_profile.py`（本模块即唯一真源）：把裸串一次性解析为 `{raw,label,regime,dynasty,period,factions,orgs,categories,office,origin,jinshi_year,note}`。实测覆盖率：**政权 1161/1231（94.3%）、官职 426、身份类别 320、派系 109、籍贯 26、科举 16**，未归类残料仅 16 条（全部落在 `note`，原串保留 `raw`）。前端 `cleanCardFields()` 改为**优先读 profile**、正则只作兜底；详情页按结构化字段分组并显示「原串：…」回查行。新规则 `V-PROFILE-01~06` 守契约（缺字段/字段不全/raw 漂移/label 空/派系拼写漂移 → ERROR） |
| P2-04 图事件监听泄漏 | ✅ | 改为**模块级 `_fgAbort`**：每次挂载前 `abort()` 上一轮再建新 controller |
| P2-05 Leaflet 失败后允许重试 | ✅ | `s.onerror` 中 **`_leafletPromise = null`** 后 reject；二轮进一步把失败变成**可见提示条 + 「重试」按钮**（见 P3-03） |
| P2-06 Leaflet 不应首页空闲预加载 | ✅ | 按用户要求**两条都保留**：① 首屏空闲后台预热；② `mouseenter` / `touchstart` 一碰地图入口就立即预热 |
| P2-07 README 主题数量不一致 | ✅ | README 与实现统一为 **墨玉 / 宣纸 / 朱砂 三套主题**（打印卡复用同一主题） |
| P2-08 工具脚本含本机绝对路径 | ✅ | 二轮清除最后两处：`.dump/_sync_docs.py` → `BASE = str(Path(__file__).resolve().parents[1])`；`.dump/_deploy_index_now.py` → `ROOT = Path(__file__).resolve().parents[1]` 推导 `LOCAL/SW/README_MD`。全部 `.dump/*.py` 已无 `D:/2026` 硬编码（`ast.parse` 全通过，脚本头执行后正确推出工程根） |
| P2-09 仓库不应存放 .workbuddy/memory | ⏸ 有意不做 | 用户既定做法：把 `.workbuddy/memory` 作为**换机接续指南**，有意保留在仓库内 |
| P2-10 URL deep link | ✅ | 首轮已支持 `#view=&person=&detail=1&event=&place=&era=&map=&q=`；二轮补齐 **`net=`（full/entity/ego）与 `from=`/`to=`（时间轴区间）**，人物搜索沿用别名解析。切换视图标签会清理上一次的实体/区间参数。无头自检新增两个场景守住 |

## 三、P3 级工程改进（3/3 完成）

| 条目 | 状态 | 落地证据 |
| --- | --- | --- |
| P3-01 index.html 体积 | ✅ | ① `--target standalone`（单文件全内嵌）/ `--target web`（`dist/<scope>/` 拆文件）双 target 保留；② 二轮**修掉一处真实缺陷**：启动守卫注释里误写了数据占位符字面量，导致整份 payload 被字符串替换注入两遍（5.6 MB → 11.4 MB）；③ 注入改紧凑 JSON（`separators=(",", ":")`）。实测 **11.39 MB → 5.13 MB（−55.0%）**，gzip 后 1.60 MB → **0.83 MB（−48%）**。防腐层：`test_data_placeholders_appear_exactly_once` + `test_compose_document_injects_payload_once` |
| P3-02 Accessibility | ✅ | tabs：`role=tablist/tab/tabpanel` + `aria-selected` + `tabIndex` + 方向键/Home/End；关系图的**文本替代**是「关系」视图的完整关系表；二轮补齐三张纯图形的替代文本：`#fullGraph` canvas 加 `role="img"` + `aria-describedby="fullSummary"` + **按当前模式动态生成**的 `aria-label`（人物图说「N 人 / M 条人物关系」，实体图说「N 个实体 / M 条关系」），人物出场热力图与中心人物网络 SVG 各加 `role="img"` + 描述性 `aria-label` |
| P3-03 统一错误 UI | ✅ | 二轮新建**统一提示条**（`role=alert`/`status` + `aria-live`，error/warn/info 三级配色，「重试」+ 关闭，按故障 key 去重）并接入 5 类失败：数据字段缺失（红）、主脚本未初始化（红，由**独立于主脚本的骨架启动守卫** 5 秒后渲染）、渲染/脚本/异步异常（红，同类只报一次，其余视图继续可用）、Leaflet CDN 失败（黄，降级离线点位图/航线图）、底图瓦片全失败（先自动 Esri→OSM 报灰，两者都不通报黄并可重试）。同步删除所有静默空 `catch`（`tests` 断言 `.catch(()=>{});` 已不存在），打印时自动隐藏。浏览器自检用「故意注入语法错误」的用例验证兜底真的会渲染 |

---

## 四、Phase 3~6 交付

| Phase | 内容 | 状态 |
| --- | --- | --- |
| Phase 3 | 统一实体 ID：`entity_id` / `relation_id`（内容寻址）/ `model.schemaVersion=3` / `idIndex` / characters 增 `profile` / payload 增 `relationGraphEntities` | ✅ |
| Phase 4 | 模板拆分：→ `web/template/index.html` + `web/css/app.css` + `web/js/app.js`；唯一注入实现 `compose_document()`；`src/build.py` 统一入口 | ✅ 逐字节等价（`test_split_is_lossless`） |
| Phase 5 | `src/validators.py` 结构不变量（**12 组**规则）+ `tests/`（**45 例**，零依赖可跑）+ `audit_final` 吸收 ERROR + `.github/workflows/ci.yml` 7 步门禁 | ✅ CI green |
| Phase 6 | URL deep link（含 `net`/`from`/`to`）/ 搜索别名命中高亮 / tabs 无障碍键盘 / 定位闪烁 / **人物图 ↔ 实体图双模式** | ✅ 完成 |

### 关系图双模式口径（Phase 6 的关键决策）

| 模式 | 节点口径 | 规模 | 读法 |
| --- | --- | --- | --- |
| 人物图（`net=full`） | 只含**人物↔人物**关系（方案 A） | 686 人 / 1403 条 | 「N 人 / M 条人物关系」+ 如实标出排除的 72 条 |
| 实体图（`net=entity`） | **全部关系端点**：人物/地点/机构/政权/其他 | 741 实体 / 1467 条 | 只能读作「N 个实体」（人物 694 + 非人物 47） |

自洽性由测试守住：**人物图的节点与边必须是实体图的子集**（1403 ⊆ 1467），两张图两次构建 sha 一致（布局纯确定性）。

### 量化改进

| 指标 | 重构前 | 重构后 |
| --- | --- | --- |
| 全量构建耗时 | 109.7 s（实测 >120 s 未完成） | **约 2.7 s** |
| `generate_report.py` 行数 | 1606 行 / 170,728 字符 | **1155 行 / 46,430 字符** |
| 前端模板位置 | Python 字符串内嵌 | `web/` 三文件独立（改前端只动 `web/`） |
| 单文件体积 | 11.39 MB（含一处占位符重复注入缺陷） | **5.13 MB（−55.0%）；gzip 1.60 → 0.83 MB** |
| 测试 | 0 | **45 / 45 通过（约 4 s）** |
| 结构校验 | 无 | `build --check`：ERROR 0 / WARNING 1 / INFO 5（**12 组规则**） |
| 深度审计 | 无分级、恒 exit 0 | INFO 17 / WARNING 2 / ERROR 0，ERROR → exit 1 |
| 关系图口径 | 741「人物」（混入 47 非人物） | **人物图 686 人 / 1403 边 / 孤立 545 / 排除 72；实体图 741 / 1467** |
| 势力字段 | 473 个裸串，前端正则猜 | **结构化 profile 全员 1231 条**，政权覆盖 94.3% |
| 别名搜索 | 0 | **444 条 aliasIndex** |
| 失败可见性 | 5 处静默空 catch | **统一提示条 + 重试**，含启动守卫兜底 |
| 无障碍 | tabs 语义 | tabs + **三张纯图形均有替代文本** |
| CI | 无 | 7 步全绿 |
| 浏览器真机验真 | 无 | 无头 Chrome **11 / 11** 场景 + 启动守卫用例 |
| 版权合规巡检 | 无 | 仓库内 **0** 命中 `chapters.json` / 原著文本 |

---

## 五、终态说明（剩余项与明确决策）

1. **唯一部分完成项 P2-02**：`from`/`to` 保留显示名是**有意决策**（姓名即全站主键，纯 id 化需要改动整条前端链路而无可见收益）。id 与显示名并存，`sourceId`/`targetId`/端点类型已在 payload 中，需要时可直接切。
2. **有意不做 P2-09**：`.workbuddy/memory` 作为换机接续指南保留在仓库内。
3. **判定不必做**：移动端详情抽屉（现有 `dialog` 已自适应 `100vw-32px` / `max-height:90vh`）。
4. **两处曾与既有约定冲突的方案项已按用户指示「都要」落地**：别名搜索、地图预热共存。
5. **非阻塞的已知遗留**（属内容考据，不是工程问题，详见 README「待办与下一步」）：41 个地点未定位、7 件事件年份待考、`延安府` 同名异地未拆分、43.6% 人物无人物间关系（不建议强补）。
