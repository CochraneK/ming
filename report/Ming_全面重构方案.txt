MING 项目全面重构方案
====================

文档用途
--------
本文件用于指导 Ming（明朝知识图谱 / 可视化报告）项目的全面重构。
目标不是推翻当前产品，而是在保留现有 GitHub Pages 单页静态部署优势的前提下，
解决当前的数据语义、构建性能、代码维护性、审计可靠性、搜索能力和测试体系问题，
并为后续继续扩展人物、事件、关系、地图、年谱和洞察功能建立稳定底座。

本文件建议作为：
1. 重构总任务书
2. GitHub Issues / Milestones 拆解依据
3. 后续 AI Agent 自动修改代码时的约束文档
4. 每一阶段完成后的验收标准

============================================================
一、重构总体目标
============================================================

当前项目已经从“Python 生成一个静态 HTML 报告”发展为一个完整的知识可视化应用，
包含人物、事件、关系、地图、时间轴、帝王、年谱、洞察、筛选、搜索、Service Worker
等功能，但源码架构仍基本沿用早期单体生成脚本模式。

本轮重构核心目标：

1. 保留最终产物尽可能简单
   - GitHub Pages 继续直接部署
   - 可继续输出单个 index.html
   - 不引入必须存在的后端服务
   - 本地可离线查看核心内容

2. 将“单体生成脚本”拆为“结构化数据 + 模块化前端 + 构建器”
   - Python 只负责数据处理、验证、构建
   - HTML 负责页面结构
   - CSS 独立维护
   - JavaScript 按功能模块维护
   - 构建阶段可重新 inline 为单文件

3. 修复当前明确的数据正确性问题
   - 全书关系图混入非人物实体
   - 孤立人物统计错误
   - 分部 scope 关系串范围
   - 审计与最终报告口径不一致
   - --dense 参数无效
   - NumPy 缺失时静默生成错误结果

4. 大幅降低构建时间
   - 去除 Python 端 800 轮 O(n²) 力导向布局
   - 避免重复计算
   - 引入必要缓存
   - 构建过程可重复、可检测、可失败

5. 建立可靠的数据模型和验证体系
   - 人物、实体、地点、政治集团、机构、政权等分类型
   - canonical name / alias 正式化
   - faction 等字段规范化
   - 所有审计复用生产代码中的同一套解析与验证逻辑

6. 改善用户体验
   - 支持别名搜索
   - 支持 URL deep link
   - 改善筛选字段质量
   - 改善关系图语义
   - 增强无障碍和移动端交互

7. 建立自动化质量门槛
   - 构建失败应返回非 0
   - 数据 invariant 可测试
   - UI 核心视图有自动化 smoke test
   - GitHub Actions 可阻止明显错误进入 main

============================================================
二、当前已确认的主要问题
============================================================

以下问题分为 P0/P1/P2/P3。
当前未发现首页直接崩溃类 P0 问题，因此重点为 P1。

------------------------------------------------------------
P1-01 全书关系图错误地将非人物实体计入“人物”
------------------------------------------------------------

当前全书图节点主要通过 relation.from / relation.to 汇总生成。
因此“出现在关系中”被错误等价为“人物”。

已确认混入的非人物实体包括但不限于：
- 东林党
- 浙党
- 东厂
- 内阁
- 后金
- 北京
- 明朝
- 元朝
- 瓦剌
- 神机营
- 黄河
- 鄱阳湖

当前页面显示：741 名人物。
实际关系图 741 个节点中，约 694 个属于人物表，约 47 个是其他实体。
这同时导致“孤立人物”统计被低估。

修复策略：

方案 A（推荐默认）：
只允许 character table 中存在的人物进入“人物关系图”。

valid_people = set(character_by_name)

graph_relations = [
    r for r in relations
    if r["from"] in valid_people
    and r["to"] in valid_people
]

方案 B：
将页面正式升级为“人物与实体关系网络”，则必须增加 entity_type，并在图上区分：
- person
- faction
- institution
- regime
- place
- event
- other

如果采用方案 B，则 UI、统计和筛选都必须同步改名，不能继续显示“741 名人物”。

------------------------------------------------------------
P1-02 孤立人物统计错误
------------------------------------------------------------

当前孤立人物约显示为 490。
按人物主表重新核算：1231 - 694 = 537。
因此真正无人物关系记录的人物约为 537。

根因：关系图 degree 的 universe 混入了非人物实体。

正确算法：

all_people = set(character_by_name)
connected_people = {
    endpoint
    for relation in person_relations
    for endpoint in [relation["from"], relation["to"]]
}
isolated_people = all_people - connected_people

验收：
页面人物总数、关系人物数、孤立人物数三者必须满足严格集合关系。

------------------------------------------------------------
P1-03 Python 端关系图布局是主要性能瓶颈
------------------------------------------------------------

当前 full graph：约 741 nodes、1467 unique edges。
Python 生成阶段执行约 800 轮 force layout，核心复杂度近似：
O(iterations × n²)，即约 800 × 741²。

实测：
- 完整生成超过 120 秒仍未完成
- 单关系布局估算约 60 秒级
- 跳过 full graph Python 力导布局后，full scope 构建约 1 秒级

并且浏览器端之后还会再次执行 force simulation，形成重复计算。

重构要求：
Python 不再负责高成本力导向布局。

推荐：
1. Python 只生成 nodes / links / degree / metadata
2. 给节点分配廉价、确定性的初始坐标
3. 浏览器运行交互式布局
4. 如果需要稳定坐标，则使用布局缓存

可选初始布局：
- 圆形
- 分层圆
- 按 faction 分区
- 简单 spiral
- seeded random

必须使用固定 seed，保证构建可复现。

------------------------------------------------------------
P1-04 NumPy“可选依赖”造成静默功能损坏
------------------------------------------------------------

当前 requirements / README 暗示项目仅依赖标准库，但 generate_report.py 会尝试 import numpy。
更严重的是，当 NumPy 不存在时，程序不会明确失败，而是静默退化，可能出现：

nodes = 741
links = 0
edges = 0

即构建表面成功、实际图数据损坏。

禁止 silent failure。

推荐处理：
直接移除 Python 力导布局，因此同步移除 NumPy 依赖。

如果未来确实需要 NumPy：
- requirements.txt 必须显式声明
- import 失败必须立即报错
- 不允许生成不完整关系图后继续发布

------------------------------------------------------------
P1-05 audit_final.py 与最终产品使用不同的数据语义
------------------------------------------------------------

例：年份为“万历末年”的事件。
audit 逻辑若仅判断 event.get("year")，会认为“有年份”；
但时间轴需要可解析 numeric year，最终会进入 unknown year。

因此出现：
audit unknown year = 6
实际最终报告 unknown year = 7

原则：
审计层不得自行重新实现生产语义。

应建立共享模块：
- src/core/year_parser.py
- src/core/entity_resolver.py
- src/core/validators.py

生产构建和 audit 必须调用同一个函数。

------------------------------------------------------------
P1-06 audit_final.py 没有覆盖最终生成后的完整数据
------------------------------------------------------------

当前 audit 检查地点数量与最终网页地点数量不一致。
例如 audit 检查约 561，最终报告约 581。
说明部分地点是在 audit 之后扩充，或 audit 与 build 使用不同的数据来源。

重构后必须建立：
RAW -> NORMALIZE -> MERGE -> VALIDATE -> FINAL MODEL -> EXPORT HTML

audit 必须检查 FINAL MODEL，而不是检查若干中间文件的近似版本。

------------------------------------------------------------
P1-07 audit_final.py 中存在未实现/无效逻辑
------------------------------------------------------------

已发现类似：

targets = set()
for ...:
    pass

随后仍输出审计结果。

这意味着部分所谓 stale geo 等检查没有真正执行。

重构要求：
1. 删除死代码
2. 每个 audit rule 必须有单元测试
3. 每个 audit rule 明确 rule_id / severity / message / affected records
4. ERROR 级问题必须 sys.exit(1)

------------------------------------------------------------
P1-08 经纬度空值判断不严谨
------------------------------------------------------------

禁止：
if not lat or not lng:

因为 0 是合法经纬度。

应改为：
if lat is None or lng is None:

并进一步检查：
- type
- range
- NaN

有效范围：
latitude: -90 ~ 90
longitude: -180 ~ 180

------------------------------------------------------------
P1-09 audit 无论发现什么都 exit 0
------------------------------------------------------------

这会导致 CI 对数据错误无感。

必须定义：
INFO / WARNING / ERROR / FATAL

建议：
if error_count > 0:
    sys.exit(1)

GitHub Actions 应运行：
python -m src.audit
python -m pytest
python -m src.build --check

任何一个失败都禁止 merge / deploy。

------------------------------------------------------------
P1-10 extract_auto.py --dense 参数无效
------------------------------------------------------------

参数已正确解析：dense = args.dense
call_model 也支持：call_model(..., dense=False)
但实际调用仍是：call_model(title, body)

必须改为：
call_model(title, body, dense=dense)

同时增加 CLI 测试：
- 默认 dense=False
- --dense => dense=True

------------------------------------------------------------
P1-11 分部 scope 关系串范围
------------------------------------------------------------

例如 p1：总关系约 1136，其中约 754 条两端人物均不属于 p1。
说明分部报告并未真正过滤 curated / derived relations。

正确 scope 策略必须先生成 allowed entity set。

如果要求纯局部图，使用：
from ∈ scope AND to ∈ scope

如果要求上下文图，使用：
from ∈ scope OR to ∈ scope

两者必须明确区分：
1. induced subgraph：两端都属于 scope
2. ego/context graph：至少一端属于 scope

UI 必须明确当前使用哪一种。

------------------------------------------------------------
P1-12 Service Worker stale-while-revalidate 生命周期不可靠
------------------------------------------------------------

若 cached response 被立即返回，后台 update promise 未通过 event.waitUntil() 保活，
浏览器可能在 worker 生命周期结束后中断更新。

应采用：

const updatePromise = fetch(request).then(...).catch(...);
event.waitUntil(updatePromise);
return cachedResponse;

必须增加版本策略：CACHE_VERSION = "ming-vX"
部署后旧缓存应可清理。

============================================================
三、P2 级重要改进
============================================================

P2-01 人物搜索必须支持 aliases
--------------------------------
当前典型问题：
朱由检 -> 可搜索
崇祯 -> 0
崇祯帝 -> 0

同理：
姚广孝 / 道衍
王守仁 / 王阳明

搜索 haystack 至少应包括：
name、aliases、role、faction、office、origin。

推荐建立 aliasIndex：
{
  "崇祯": "朱由检",
  "崇祯帝": "朱由检",
  "王阳明": "王守仁"
}

所有模块共用。

P2-02 建立统一实体解析系统
--------------------------
未来关系数据不能只使用裸字符串。

推荐：
{
  "id": "person:zhu-youjian",
  "name": "朱由检",
  "type": "person",
  "aliases": ["崇祯", "崇祯帝", "信王"]
}

关系使用 source_id / target_id，而不是纯显示名。
优点：避免同名冲突、类型可检查、scope 可准确筛选、实体合并更安全。

P2-03 faction 字段必须规范化
----------------------------
当前约 1231 人物产生约 473 个 faction 字符串，说明字段混入大量非派系信息。

推荐结构：
{
  "faction": ["东林党"],
  "faction_raw": "...",
  "dynasty": "明",
  "office": ["兵科给事中"],
  "origin": "湖广应山",
  "jinshi_year": 1607
}

UI 不应通过字符串正则猜字段含义。

P2-04 图事件监听存在潜在泄漏
----------------------------
AbortController 应放模块级/实例级变量，不应绑在即将被替换的 canvas DOM 上。
每次 mount 前 abort 上一个 controller，unmount 时清理。

P2-05 Leaflet 首次加载失败后应允许重试
--------------------------------------
若 _leafletPromise 首次 reject，必须在 catch 中置回 null，否则网络恢复后仍无法加载。

P2-06 Leaflet 不应首页空闲即预加载
----------------------------------
推荐仅在：hover 地图 tab、touchstart 地图 tab、第一次进入地图时加载。

P2-07 README 与真实主题数量不一致
---------------------------------
README 若写墨/纸/朱砂/玉 4 主题，而实际只有 3 个，应补功能或改文档。

P2-08 工具脚本包含本机绝对路径
--------------------------------
所有路径应基于 Path(__file__).resolve() 和 PROJECT_ROOT 构造。
禁止硬编码 D:/... 等本机目录。

P2-09 公开仓库不应长期存放 .workbuddy/memory
-------------------------------------------
建议加入 .gitignore：
.workbuddy/
*.local
.env
.env.*

P2-10 URL deep link
-------------------
建议支持：
#view=characters&q=崇祯
#view=relations&person=朱元璋
#view=timeline&from=1368&to=1644
#view=map&place=北京

============================================================
四、P3 级工程改进
============================================================

P3-01 index.html 体积
--------------------
当前单文件 HTML 原始约 4 MB 级，主体是内嵌 DATA。
不建议为了减小文件强行引入后端。

建议支持两种 build target：
1. standalone：单 index.html，全内嵌
2. web：index.html + assets/app.js + assets/app.css + data.json

GitHub Pages 可用 web target，release 附件提供 standalone。

P3-02 Accessibility
-------------------
tab 应使用 role=tablist / tab / tabpanel、aria-selected、aria-controls、tabindex。
canvas 关系图至少要有文本替代视图。

P3-03 统一错误 UI
-----------------
Leaflet、地图瓦片、数据解析、Service Worker 更新失败均应有用户可见错误与重试入口。

============================================================
五、目标源码架构
============================================================

ming/
├─ README.md
├─ requirements.txt
├─ pyproject.toml
├─ .gitignore
├─ .github/workflows/
│  ├─ test.yml
│  └─ deploy.yml
├─ data/
│  ├─ raw/
│  ├─ curated/
│  ├─ generated/
│  └─ cache/
├─ src/
│  ├─ build.py
│  ├─ audit.py
│  ├─ core/
│  │  ├─ models.py
│  │  ├─ normalize.py
│  │  ├─ year_parser.py
│  │  ├─ entity_resolver.py
│  │  ├─ scope.py
│  │  └─ validators.py
│  ├─ loaders/
│  │  ├─ characters.py
│  │  ├─ events.py
│  │  ├─ relations.py
│  │  ├─ places.py
│  │  └─ emperors.py
│  ├─ enrich/
│  │  ├─ aliases.py
│  │  ├─ geo.py
│  │  ├─ factions.py
│  │  └─ relations.py
│  ├─ graph/
│  │  ├─ person_graph.py
│  │  ├─ entity_graph.py
│  │  └─ metrics.py
│  └─ export/
│     ├─ html.py
│     └─ json.py
├─ web/
│  ├─ template/index.html
│  ├─ css/
│  │  ├─ base.css
│  │  ├─ layout.css
│  │  ├─ components.css
│  │  └─ responsive.css
│  └─ js/
│     ├─ app.js
│     ├─ state.js
│     ├─ router.js
│     ├─ search.js
│     ├─ characters.js
│     ├─ relations.js
│     ├─ map.js
│     ├─ timeline.js
│     ├─ charts.js
│     └─ utils.js
├─ tests/
│  ├─ test_year_parser.py
│  ├─ test_entities.py
│  ├─ test_relations.py
│  ├─ test_scope.py
│  ├─ test_audit.py
│  └─ browser/smoke.spec.js
├─ scripts/
│  ├─ extract_auto.py
│  └─ migrate_data.py
└─ dist/
   └─ index.html

============================================================
六、数据层重构
============================================================

必须明确数据处理层级：

RAW
原始抽取数据，尽可能保留来源原貌，不得由 UI 直接消费。

NORMALIZED
字段标准化：ID、canonical name、aliases、year、coordinates、type、faction、office、origin。

CURATED
人工校正。人工校正优先级高于自动抽取。

FINAL MODEL
所有页面共用的唯一真源。

建议：
{
  "characters": [...],
  "events": [...],
  "relations": [...],
  "places": [...],
  "emperors": [...],
  "indexes": {
      "alias_to_entity": {...},
      "character_by_id": {...}
  },
  "stats": {...}
}

页面统计不得各自临时重新推导不同口径。

============================================================
七、推荐实体 Schema
============================================================

Person：
{
  "id": "person:...",
  "type": "person",
  "name": "...",
  "aliases": [],
  "birth_year": null,
  "death_year": null,
  "dynasty": "明",
  "factions": [],
  "offices": [],
  "origin": null,
  "description": "",
  "sources": []
}

Place：
{
  "id": "place:...",
  "type": "place",
  "name": "...",
  "aliases": [],
  "lat": null,
  "lng": null,
  "modern_name": null,
  "sources": []
}

Organization / Faction：
{
  "id": "org:...",
  "type": "organization",
  "subtype": "faction",
  "name": "...",
  "aliases": []
}

Relation：
{
  "id": "relation:...",
  "source_id": "...",
  "target_id": "...",
  "type": "...",
  "label": "...",
  "year_start": null,
  "year_end": null,
  "confidence": null,
  "sources": []
}

Event：
{
  "id": "event:...",
  "title": "...",
  "year_raw": "...",
  "year": null,
  "year_start": null,
  "year_end": null,
  "participants": [],
  "places": [],
  "description": "",
  "sources": []
}

============================================================
八、构建流程重构
============================================================

建议统一入口：
python -m src.build

支持：
python -m src.build --scope full
python -m src.build --scope p1
python -m src.build --target standalone
python -m src.build --target web
python -m src.build --check

流程：
1. load raw
2. normalize
3. resolve entities
4. merge curated corrections
5. enrich
6. build indexes
7. validate
8. compute stats
9. export data
10. render template
11. inline assets（standalone 模式）
12. final validation

构建输出必须包含摘要：
Characters / Events / Relations / Places / Unknown years / Unresolved entities / Warnings / Errors / Elapsed

============================================================
九、关系图重构
============================================================

建议正式分成两种：

A. 人物关系网络
节点只允许 person。
用于研究人物社交、政治、亲属、军事等关系。

B. 实体知识图谱
允许 person / faction / institution / place / regime。
必须通过 shape / color / legend 区分类型。

不要将二者混在一起但仍叫“人物关系图”。

Python 只输出：ids、links、degree、type、label、optional community。
布局由浏览器完成。

700~1500 节点建议：
1. 初始圆形/分区布局
2. requestAnimationFrame 分批模拟
3. 限制 force ticks
4. zoom 时动态 label
5. 默认只显示高 degree label
6. 提供人物搜索定位

============================================================
十、搜索系统重构
============================================================

统一 search(query, filters)。
建立 searchableText：name + aliases + faction + role + office + origin + description。

优先级：
1. exact canonical
2. exact alias
3. prefix
4. substring
5. description substring

第一阶段无需引入全文搜索库，纯 JS 足够。

============================================================
十一、前端状态管理
============================================================

建立统一 state：
{
  view: "overview",
  query: "",
  filters: {},
  selectedEntity: null,
  timelineRange: null
}

提供 setState(partial) / subscribe(listener)。
小项目不需要 Redux。
URL router 与 state 双向同步。

============================================================
十二、模板与前端拆分
============================================================

不要继续在 Python 三引号中维护大段 HTML/CSS/JavaScript。
应拆为独立文件。

build 时读取 template、CSS、JS、DATA，再替换：
{{INLINE_CSS}}
{{INLINE_JS}}
{{INLINE_DATA}}

这样保留“单 HTML 发布”的优势，同时开发时拥有正常语言文件。

============================================================
十三、Service Worker 重构
============================================================

建议仅缓存：index.html、必要 assets、可选字体。
外部地图瓦片不要无限缓存。

策略：
HTML：network-first / stale fallback
静态 assets：cache-first + version
第三方 CDN：stale-while-revalidate

要求：
- event.waitUntil
- versioned cache
- activate 删除旧 cache
- fetch error fallback
- 更新通知可选

standalone 模式甚至可不注册 SW。

============================================================
十四、测试体系
============================================================

1. Data invariant tests
- 所有人物 id 唯一
- canonical name 非空
- alias 不得映射多个实体（除非显式允许）
- relation source/target 必须存在
- 人物图 source/target 必须都是 person
- 经纬度合法
- year parser 结果合法
- scope 过滤准确

2. Regression tests
固定人物：朱由检、王守仁、姚广孝、朱元璋。
断言 alias 可搜索、canonical 正确、关键事件和关系存在。

3. Build tests
full、p1~p7 都必须成功。
无 NumPy 环境构建结果不能变化。

4. Browser smoke tests
依次打开 12 个主要视图，断言：
- 无 pageerror
- 无 console error
- 每页关键 DOM 存在
- 移动端无全页横向 overflow

5. Search tests
崇祯 => 朱由检
王阳明 => 王守仁
道衍 => 姚广孝

============================================================
十五、GitHub Actions
============================================================

PR / push 自动运行：
1. Python syntax
2. pytest
3. audit
4. full build
5. p1-p7 build
6. browser smoke
7. 检查 dist
8. 发布 Pages

部署只能来源于通过测试的 build artifact。
不要直接把人工更新的 index.html 当唯一部署真源。

============================================================
十六、重构阶段规划
============================================================

Phase 0：冻结与基线
-------------------
- 保存当前 index.html
- 截取主要页面截图
- 保存现有统计量
- 记录 12 个主视图
- 建立 smoke baseline
- 标记 README 已知遗留问题

Phase 1：Correctness Hotfix
--------------------------
1. 修 --dense
2. 修人物关系图 entity 口径
3. 修孤立人物统计
4. 修 scope relation
5. 修 lat/lng 判断
6. 修 audit exit code
7. 修未实现 audit 规则
8. 修 Service Worker waitUntil
9. 修 alias search

Phase 2：移除 Python 力导布局
----------------------------
1. 删除 Python 800 ticks
2. 删除 NumPy fallback
3. deterministic initial layout
4. 浏览器负责 force simulation
5. 对比构建时间

目标：full build 从分钟级降至秒级。

Phase 3：统一数据模型
--------------------
1. canonical IDs
2. entity types
3. alias index
4. normalized faction
5. unified year parser
6. unified geo schema
7. relation IDs
8. final model

Phase 4：拆 generate_report.py
-----------------------------
1. HTML template 独立
2. CSS 独立
3. JS 独立
4. generate_report -> build/export
5. standalone/web target

Phase 5：Audit + Test + CI
-------------------------
1. validators
2. pytest
3. browser smoke
4. GitHub Actions
5. build artifact deploy
6. error/warning severity

Phase 6：UX Enhancement
----------------------
1. alias 搜索
2. URL deep link
3. 搜索高亮
4. 关系图图例
5. 人物/实体图切换
6. 筛选器规范化
7. mobile detail drawer
8. accessibility

============================================================
十七、不建议现在做的事情
============================================================

1. 不建议立即迁移 React/Vue
   当前规模用原生 JS + 模块化足够。

2. 不建议立即上数据库/后端
   静态知识站点仍可支撑当前规模。

3. 不建议继续增加大量新页面
   当前短板不是页面数量。

4. 不建议为了性能删除已有丰富数据
   当前真正瓶颈是生成算法，不是数据量本身。

5. 不建议同时重写数据、UI、构建和设计
   应按阶段迁移，保持每个 commit 可运行。

============================================================
十八、推荐 Git 提交策略
============================================================

fix: pass dense flag to model extraction
fix: restrict person graph to character entities
fix: correct isolated person statistics
fix: scope relation filtering
fix: service worker background update lifecycle
perf: remove python force-directed graph layout
refactor: introduce shared year parser
refactor: introduce entity resolver
refactor: normalize final data model
refactor: extract html template
refactor: extract frontend javascript modules
test: add data invariant tests
test: add browser smoke tests
ci: add build and audit workflow
feat: support alias search
feat: add url state routing

============================================================
十九、最终验收标准
============================================================

构建：
[ ] full build < 10 秒（合理硬件，不含外部 AI 抽取）
[ ] 不依赖 NumPy
[ ] p1-p7 均正常构建
[ ] 构建可重复

数据：
[ ] 人物图无非人物节点
[ ] 实体图类型明确
[ ] relation 无悬空 endpoint
[ ] unknown year 口径统一
[ ] geo 数量 audit == final
[ ] faction 可稳定筛选

搜索：
[ ] 崇祯 -> 朱由检
[ ] 王阳明 -> 王守仁
[ ] 道衍 -> 姚广孝
[ ] aliases 全局统一

前端：
[ ] 12 个视图无 JS error
[ ] 390px 移动端无全局 overflow
[ ] map CDN 失败可重试
[ ] relation graph 重建无 event leak
[ ] URL 可分享当前 view

Service Worker：
[ ] cache version 正常升级
[ ] 后台 revalidate 使用 waitUntil
[ ] 旧缓存自动清理

工程：
[ ] tests 可运行
[ ] audit ERROR 返回非 0
[ ] GitHub Actions 可阻止坏构建发布
[ ] 页面模板不再维护在 Python 大字符串内

文档：
[ ] README 与真实功能一致
[ ] 依赖声明真实
[ ] 构建命令统一
[ ] 数据模型文档化

============================================================
二十、建议的实际执行优先级
============================================================

最高优先：
1. 修 --dense
2. 修人物图实体混入
3. 修孤立人物统计
4. 修 scope relation
5. 修 audit 口径
6. 修 audit exit code
7. 修 Service Worker
8. alias 搜索

第二优先：
9. 删除 Python force layout
10. 删除 NumPy fallback
11. 建立共享 year parser
12. 建立 entity resolver
13. faction normalize

第三优先：
14. 拆 HTML/CSS/JS
15. build.py 统一入口
16. automated tests
17. CI/CD

第四优先：
18. deep link
19. accessibility
20. 人物图 / 实体图双模式
21. 搜索体验增强

============================================================
二十一、最终架构原则
============================================================

原则 1：最终页面可以简单，但源码不能继续单体化。
原则 2：UI 不负责修脏数据。
原则 3：统计必须来自统一 final model。
原则 4：audit 与生产构建必须复用同一套解析代码。
原则 5：“构建成功”必须意味着数据有效，而不仅是没抛异常。
原则 6：人物、地点、组织、政权等实体必须有类型。
原则 7：canonical name 与 alias 必须分离。
原则 8：重型图布局不应在 Python 构建阶段重复执行。
原则 9：所有 scope 都必须有严格定义和自动测试。
原则 10：任何会影响发布的错误必须能够在 CI 中失败。

============================================================
二十二、重构完成后的理想状态
============================================================

开发者执行：
python -m src.build --target standalone

几秒内得到：
dist/index.html

同时：
python -m src.audit

输出类似：
Characters .......... 1231
Events .............. XXXX
Relations ........... XXXX
Places .............. XXXX
Unknown years ....... X
Unresolved aliases .. 0
Broken relations .... 0
Invalid coordinates . 0
Warnings ............ X
Errors .............. 0

GitHub push 后：
Tests -> Audit -> Build -> Browser smoke -> Deploy Pages
全部自动完成。

最终用户仍然只看到一个快速、完整、无需后端的明朝知识可视化网站。

本次重构的核心目标不是把项目复杂化，而是让复杂度从“隐式、混乱、难验证”
变成“显式、模块化、可测试、可持续扩展”。

—— Ming 全面重构方案
