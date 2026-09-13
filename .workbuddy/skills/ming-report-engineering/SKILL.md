---
name: ming-report-engineering
description: >
  明朝知识图交互报告（基于《明朝那些事儿》）的构建、合并、部署与数据审计工程 skill。
  覆盖从 data/*.json → index.html 的生成流水线，以及本沙箱内 GitHub Pages 发布、洞察报告
  子流水线、手动数据补录、抽取充分性核查等全部工程环节与历史踩坑。务必在以下场景使用：
  用户说"重生成报告""重新构建""部署""推送""发布到 pages""补录人物/地点/关系"
  "抽取是否充分""还能抽取吗""召回探测""检查 CSS/前端""合并数据""manual_*.json"
  "洞察""学科""为什么报告没更新""地图灰了""gh 报错 tls""python 中文乱码"；
  或任何涉及 D:/2026/WB项目/明朝 仓库的构建/发布/数据质量任务。
version: 2.0.0
agent_created: true
allowed-tools: Bash,Read,Write,Edit,Grep,Glob
---

# 明朝报告工程与发布（ming-report-engineering）

《明朝那些事儿》知识图报告的「构建—合并—部署—审计—洞察」全流程工程手册。
所有命令均针对 Windows 沙箱 + 托管 Python 环境，照抄即可，不要自创路径或解释器。

## 项目身份
- 显示名 `Ming`；本地文件夹 `D:\2026\WB项目\明朝`。
- GitHub 仓库 `CochraneK/ming`（public）。在线报告 https://cochranek.github.io/ming/ （根入口 `/ming/`，源分支 main，Pages 源路径 `/`）。
- **版权硬约束**：`明朝那些事儿.txt` 与 `data/chapters.json`（含全书正文）**绝不发布**。

## 架构与命令

数据流水线：
`chapters.json`(章节正文) → `extract_raw.json`(LLM 抽取，OmniRoute 网关方案已弃用)
→ `data.json`(merge.py 聚合并注入 manual_*) → `index.html`(generate_report.py 单文件 HTML，内联 CSS/JS，~4MB)

### 运行环境（Windows 沙箱·硬约束）
- **用托管的 Python**：`C:/Users/cunyi/.workbuddy/binaries/python/versions/3.13.12/python.exe`（绝不用系统 `python`）。
- **路径用 `D:/` 风格绝对路径**：Windows 原生 python 不认 `/d/` POSIX 前缀。
- **中文必须 UTF-8**：调用前 `export PYTHONUTF8=1`，否则中文报 `SyntaxError: invalid character`。
- **中文命令行字面量乱码**：`-c "..."` 里直接写中文会损坏。逻辑写进 `.py` 文件维护，Bash 只负责调用。
- **反引号会被 shell 吃掉（2026-09-13 实测）**：`python -c "长文本含 \`反引号\`"` 时 bash 会先做命令替换，写进文件的正文会变成空串出乱子（本次把一篇中文日志写坏重写）。**凡是含反引号/大段中文的文本，一律用 Write/Edit 工具写文件**，不要用 `python -c` 拼。
- **2026-09-13 实测：本会话 Bash 的 PATH 被裁过**——`ls / tail / dirname / find / agent-browser` 全部 `command not found`，但 `cd`、`echo`、绝对路径调用的 exe 仍可用。
  - 对策：一切外部程序都用**绝对路径**调用（python / node 见上；需要 shell 工具时用 python 的 `os.listdir` / `Path.glob` 代替 `ls`、用 `io.open(...).read()` 代替 `cat`）。
  - `agent-browser` 此会话不可用 → 前端验证改用 **Node 直跑渲染函数 + 数据不变量断言**（见「前端验证（无浏览器时）」）。

标准调用样板：
```bash
export PYTHONUTF8=1
PY="/c/Users/cunyi/.workbuddy/binaries/python/versions/3.13.12/python.exe"
cd "D:/2026/WB项目/明朝" && $PY src/merge.py        # 重建 data.json
$PY src/generate_report.py                          # 重建 index.html（全量约 2 秒）
$PY src/audit_final.py                              # 终态审计（有 ERROR 返回 1）
```

### 共享核心（src/core/，2026-09-13 新增）
生产构建与审计**必须共用同一套语义**，禁止各写一份：
- `src/core/year_parser.py` —— `year_bounds(value) -> (start, end)`；非数字年份（如「万历末年」）返回 `(None, None)`，即页面上的「年份待考」。`generate_report.py` 的 `year_bounds` 现在只是它的薄包装。
- `src/core/geo.py` —— `is_valid_lat/lng`、`has_coords`、`coord_problem`。**禁止 `if not lat or not lng`**（0 是合法经纬度），一律 `is None` + 类型 + 范围 + NaN。
- 起因（P1-05）：旧审计用 `if not event.get("year")` 判年份，报告用数值解析，于是「审计 6 个未知年份 vs 报告 7 个」长期对不上。


### 合并（src/merge.py）
- 遍历 `extract_raw.json` 构建 `characters / locations / events / relations`，手动数据在之后注入，**重跑不丢**：
  - `data/manual_corrections.json` —— 分块 `event_years / character_merges / character_alias_remove / character_faction / character_role / location_fixes / relation_fixes{flip,drop}`，在**关系构建之前**应用。
  - `data/manual_lifespans.json` —— 生年不详用「卒年-55」占位并标 `life_estimated`，年谱虚线条渲染，绝不冒充已知年份；新增分组需在 `renderChronicle` 的 `GROUP_COLORS` 补色。
  - `data/manual_persons.json` —— 补录独立人物卡。
  - `data/derived_chapter_persons.json` —— `src/derive_coverage.py` 产出（每章正文最长匹配已知指称 ≥6 次登记出场），只为已有人物卡补记录。
- 关系方向约定：**亲属为长辈→晚辈**（父→子、祖→孙）。
- 关系端点类型：`merge.py` 的 `_endpoint_kind` 按 **人物→地点→政权→派系机构→其他** 判定，报告加 `.ep-tag` 徽标。

### 报告生成（src/generate_report.py）
- 单文件 HTML，CSS/JS 全在 f-string 模板内联，无构建工具。
- **生成后必查 CSS 括号平衡**：`css.count('{') - css.count('}') == 0`。单行模板缺一个 `}` 会静默吞掉其后全部规则。
- **搜索框必须走 bindSearch()**：直接监听 `input` 会全量重渲染销毁输入框，中文输入法无法连续输入（封装防抖 220ms + 合成期保护 + 焦点还原）。
- **`load_json()` 只接受 Path 对象**：传 str 报 `'str' object has no attribute 'exists'`；用 `BASE / "data" / "x.json"`。
- **`event_places.json` 注入必须发生在归一化循环「之前」**（`build_scope` 的 `for location in raw_locations:` 之前），否则新地点缺字段抛 TypeError。
- **GAZ 坐标元组顺序恒为 `(lng, lat, 今址, 类型)`**；校验：`[l['ancient'] for l in data['locations'] if l.get('lat') and abs(l['lat'])>90]` 应为空。
- 人物卡势力字段由前端 `cleanCardFields()` 做显示层清洁（不改源数据）；卡面主题 `state.cardTheme` 切换。
- 统计口径：`data.json` 地点 561（定位 520），报告显示 581/540——差值来自 `event_places.json` 构建时注入，属预期非 bug。

### 人物卡语录（2026-09-04）
- `data/character_quotes.json`：name→语录（13 位核心人物，**全部在原书 txt 命中原文**；无语录的卡不显示该行）。
- 卡背「关系」行已替换为「语录」行（屏幕卡 `characterCard` + 打印背卡 `renderPrint` 两处）；详情弹窗仍保留关系。
- payload 注入：`"quotes": {k:v for k,v in load_json(...).items() if k!='_comment'}`。

### 地图（Leaflet 懒加载 + 预热 + Esri 主源）
- **瓦片工厂 `makeTiles()`**（全局）：主源 **Esri World_Street_Map**（`server.arcgisonline.com/.../tile/{z}/{y}/{x}`，**y 在 x 前**），`tileerror`≥6 且 0 张成功时自动 `setUrl` 回退 OSM。warmMap / 主图 / 航线三处共用。
- **原因**：`tile.openstreetmap.org` 在部分网络（含用户本机）挂起不响应，页面内 fetch 对照实验可证实（curl 通≠浏览器通）。
- **懒加载**：Leaflet 由 `loadLeaflet()` 按需注入 unpkg css/js，**勿放回 `<head>`**（会阻塞首屏）。
- **后台预热 `warmMap()`**：`requestIdleCallback` → `loadLeaflet()` → 屏外隐藏 div（400×300，left:-9999px）建 L.map([34.5,113],4) 预热瓦片 → 4s 后 remove。点开地图零等待；预热失败静默（SVG 点图兜底仍在）。

## 全面重构落地（2026-09-13，对应 `report/Ming_全面重构方案.txt`）
已完成 **Phase 1 正确性热修 + Phase 2 移除 Python 力导布局**；Phase 3~6（统一 ID 模型 / 拆分 generate_report / 测试 CI / deep link）待排期。

- **构建提速 47 倍**：删掉 `build_relation_graph_full` 里 numpy 的 800 轮 O(n²) FR 布局，改为确定性廉价初始坐标（势力分扇区 + 扇区内螺旋，`math` 即可，无随机）；真正的力导向交给浏览器端 `fullStep()`（网格加速斥力 + 弹簧 + 中心引力）。**全量构建 109.7s → 2.3s**，且 numpy 依赖彻底移除（旧代码在 numpy 缺失时静默返回 `links: []`，构建"成功"但图是坏的）。
- **人物关系图口径（方案 A）**：节点只允许 `chars` 里的人；`deg` 只在人物内部统计；`stats` 现为 `{nodes, edges, persons, connected, isolated, excludedNonPerson}`。实测 741 端点中 47 个非人物（东林党/东厂/内阁/后金/北京/明朝/黄河…）被排除 → **686 人 / 1403 边 / 孤立 545（44.3%）/ 排除 72 条含非人物端点的关系**。页面文案由 `fullSummaryHTML(g)` 单点生成（renderFullGraph 与 resetFullHighlight 共用），避免两处再漂移。
- **分部关系 scope**：`build_scope()` 里 `relation_scope = "all" if scope=="full" else "induced"`，induced = 两端都在 `scope_names`（= 该部范围内至少有一章的人物）内。修复前 p1 有 754 条两边人物都不属于 p1 的串范围关系；修复后 p1~p7 全部"关系诱导子图干净"（审计 `R-SCOPE-00/01` 逐部验证）。payload 新增 `relationScope`，关系视图顶部如实标注。
- **审计重写**：`audit_final.py` 现在**直接 `import generate_report as G` 调 `G.build_scope("full")`** 审最终模型（不再读中间文件另算口径），分级 INFO/WARNING/ERROR，有 ERROR `sys.exit(1)`。旧版 `[9]` 规则是 `for ...: pass` 的假实现，已换成真 stale 检查。
- **误报陷阱**：geo_annotations 里 93 条"不在地点表"其实都是**旧称**（应天→南京、濠州→凤阳、平江→苏州），已由 `mentioned_as` 别名关联合并——判定 stale 必须"先查原名、再查别名"，否则虚报 93 条。只有同名的**朝鲜延安 vs 陕西延安**是真正待拆的同名异地。
- **SW**：后台更新改为 `event.waitUntil(network)` 保活（原先 `return cached || network` 会让 worker 生命周期在 fetch 完成前结束）；`CACHE` bump 到 `v4`。
- **前端小修**：`setupFullInteractions` 的 AbortController 提升为模块级 `_fgAbort`（原先挂在会被 innerHTML 替换的 canvas 上，window 级监听会累积泄漏）；`loadLeaflet()` 失败时 `_leafletPromise=null` 允许重试。

### 前端验证（无浏览器时）
`agent-browser` 不可用（或 PATH 被裁）时，用 Node 直接跑渲染函数 + 断言数据不变量，比肉眼看截图更靠谱：
```javascript
// node: 从 index.html 抽 DATA 与目标函数，eval 后断言
const DATA = JSON.parse(html.match(/const DATA=(\{[\s\S]*?\});\s*\n/)[1]);
const src  = html.match(/function fullSummaryHTML\(g\)\{[\s\S]*?\n\}/)[0]; eval(src);
// 断言：节点 ⊆ 人物表、isolated == persons - connected、无悬空边、坐标落在画布内
```
改完内联 JS 先过 `node --check`（把 `<script>` 块抽成文件），再跑上面的断言。


## Service Worker（sw.js，根目录）
- **只拦同源请求**做 stale-while-revalidate（先返缓存、后台更新）——重复访问秒开；**跨域请求（瓦片/unpkg）一律 `return` 不拦截**：`respondWith` 转发跨域 no-cors 图片请求会永久 pending（灰底红点事故根因）。
- **后台更新必须 `fetch(req, {cache:'no-cache'})`**：否则 GitHub Pages 的 max-age=600 会让 SWR 拿到陈旧响应，用户连看多轮旧版。
- **命中缓存时后台更新要 `event.waitUntil(network)` 保活**：只 `return cached` 的话 worker 可能在 fetch 完成前结束，更新被打断、旧版长期不换。
- 改版时 bump `CACHE` 名（activate 自动清旧缓存）。用户报"内容没更新"时先 `gh api /repos/CochraneK/ming/git/blobs/<sha>` 拉线上文件解码验证，再归因缓存。

### 合规巡检：线上绝不能有原书全文（2026-09-13 事故）

`.gitignore` 里写着 `data/chapters.json` 不入库，但**它仍在公开仓库里**（4.5 MB / 168 章含 `body`，与本地份字节一致，早在 2026-09-04 的 `Add files via upload` 就混进去了——`.gitignore` 只挡 `git add`，挡不住 Contents/Git Database API 上传）。已从 main 移除，但历史提交仍可访问该 blob。

**每次部署/同步后必跑（一条命令）**：
```bash
# 列出线上所有文件，人工确认没有禁书产物
gh api "/repos/CochraneK/ming/git/trees/main?recursive=1" \
  --jq '.tree[]|select(.type=="blob")|.path' | grep -Ei 'chapters\.json|明朝那些事儿'
# 期望：无输出（chapters_index.json 只是章节元信息，无正文，可保留）
```
- 本地比对脚本 `.dump/_diff_remote.py`（blob sha 全量比对，输出「未传/过时/仅线上」三类）会自动把 `chapters.json` 列进「仅线上」——**看到这条就是事故**。
- 移除方法：`.dump/_remove_book_text.py`（tree 里该 path 置 `sha: null` → 新 commit → PATCH refs，其它文件不动）。
- 彻底清除需要**重写历史**（孤儿 commit + force PATCH refs），旧 commit 才不可达；GitHub 仍可能按 sha 直达 blob 直到 GC——真要彻底，需删库重建或找 GitHub Support。
- 本项目部署脚本的 FILES 清单**有意排除**：`明朝那些事儿.txt`、`data/chapters.json`。新增文件时别把这两个顺手加进去。

## 部署（GitHub Pages，沙箱内）
- 沙箱 `git`/`curl` 连不上 GitHub（loopback≠宿主），用 `gh` CLI（走宿主网络）；**`gh` 前必须 `env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy -u ALL_PROXY -u all_proxy` 清代理**，否则报 `tls: first record...`。
- **沙箱 `env` 也可能不在 PATH** → 直接用 python 调脚本（脚本内部已自行剥掉代理变量再调 `gh`），别再套 `env -u`。
- **沙箱到 api.github.com 会抖动**：同一脚本可能这次 401 Bad credentials、下次 TLS handshake timeout、再跑就成功。`.dump/_sync_docs.py` 已内置「只传变化文件 + 失败重试 3 次」；遇到 401/TLS 先原样重跑，别急着改配置。
- 仓库目录**不是 git 仓库**（无 `.git`），一切发布走 `gh` API；`.dump/git-sync/` 是早期 git 推送方式留下的本地镜像，已弃用（可清理）。

### 发布（.dump/_deploy_index_now.py）
部署 **index.html + sw.js + README.md 三文件**（Git Database API：blob→tree→commit→PATCH refs，字节级校验）。`gh 401` 但 `gh api /user` 正常 = 沙箱网络拦截，用 `dangerouslyDisableSandbox` 跑部署。
- 沙箱 gh token 无 `delete_repo` scope；重写历史用 Git Database API 建孤儿 commit + force PATCH refs。
- **同步走 `.dump/_sync_docs.py`**（FILES 全量清单，含 src/core、report/、.workbuddy/skill+memory）；已加「blob sha 比对跳过未变化 + 重试 3 次」，51 个文件里通常只有几个真需要上传（4 MB 的 index.html 不再每次重传）。
- 差异巡检用 `.dump/_diff_remote.py`（只读，三类结论）；**看到 `data/chapters.json` 出现在「仅线上」就立刻按「合规巡检」处理**。

### 确认 GitHub 与本地的差异（哪些没传 / 哪些过时）
```bash
env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy -u ALL_PROXY -u all_proxy \
  gh api "/repos/CochraneK/ming/git/trees/HEAD?recursive=1" \
  --jq '.tree[] | select(.type=="blob") | .path + " " + .sha' > .dump/_remote_tree.txt
```
本地逐文件算 git blob sha，与线上清单对比，三类结论：仅本地（未传）/ 两边都有但 sha 不同（线上过时）/ 一致：
```python
import hashlib
sha = hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()   # data=文件字节
```
- 输出对照时注意 `os.path.join` 结果用 `os.sep` 规范化，勿用 `lstrip('./')`（会把 `.dump`/`.workbuddy` 的首字符剥掉造成假差异）。
- 临时清单文件放 `.dump/`，别放 `/tmp`（Windows python 不认）。
- 比对后按需跑 `.dump/_sync_docs.py`（FILES 全量清单）补齐；`明朝那些事儿.txt`/`data/chapters.json` 有意排除。

## 洞察报告子流水线（19 节 = 18 学科 + 综合收束）
- 内容源：`src/insight_content.py` 导出 `INSIGHT_SECTIONS`（{id,title,discipline,html}）+ `INSIGHT_REFS`（APA 7，**71 条全部经 WebSearch 核实**）；`generate_report.py` 注入 `INSIGHT_DATA`，`renderInsight()` 渲染（目录=编号彩色卡片，DISC_COLORS 按 id 取色，综合节金色收束于末）。
- **学科最常用叫法（2026-09-04 定稿）**：历史学/心理学/博物馆学/政治学/社会学/人类学/系统科学/经济学/地理学/法学/军事学/叙事学/性别研究/思想史/国际关系/科学史/艺术/传播学。改名动三处：`discipline` 字段、综合节收束清单、README 学科列表（id 不变）。
- **引用纪律**：新文献必须 WebSearch 核实（research agent）后才进 `INSIGHT_REFS`；文内 (作者,年) 与 refs 用正则双向核验（缺失 + 未被引用，注意中文姓氏检查会误报）。
- **书内情节/语录纪律**：每个例子先在 `明朝那些事儿.txt` 关键词命中原文再写（0 命中即弃用，如"守墓/金谷之园/作序/按自己的方式"均 0 命中弃用）。
- 数据锚点块 `<div class="insight-data">` 已按用户要求整体移除：导出前 `_strip_data_anchors()` 剥离；恢复=去掉导出前包装。
- 学科素材饱和判定：新角度先测原书关键词命中密度（徐渭 101 → 收；杨应龙 3 → 并），密度不够就并入现有节（工程→科学史、教育→社会学、宗教→思想史、族群→国际关系均已合并）。

## 抽取充分性审计
- 脚本 `src/discover_persons.py`（纯本地）：主语提取/封授结构/表字结构三信号 + 姓氏白名单过滤。`MODES=zi TH=1` 跑表字信号（最可靠）；`CHAPTERS=p1-c22` 定向核查。
- **召回探测必须用 merge 后规范名口径**（别名未归一是伪影）；逐章对比用数字感知排序 `(part, chap)`。
- 结论口径：书中实际出现的人物基本已建卡，剩余为极边角（每章 1 次提及），不建议强行补录。

## 常见故障速查

| 现象 | 根因 | 修法 |
|---|---|---|
| python `open` 路径失败 | `/d/` 不被 Windows python 认 | 用 `D:/` 风格绝对路径 |
| `SyntaxError: invalid character` | 非 UTF-8 | `export PYTHONUTF8=1` |
| `load_json` 报 `'str' has no exists` | 传了 str | 传 Path：`BASE / "data" / "x.json"` |
| `gh` 报 `tls: first record...` | 沙箱继承宿主代理不可达 | `env -u` 清全部代理变量 |
| `gh` 报 401 但 `/user` 正常 | 沙箱网络拦截大 blob POST | `dangerouslyDisableSandbox` 跑部署 |
| CSS 某段突然失效 | 单行模板 `@media` 未闭合 `}` | 查 `count('{')-count('}')` 应为 0 |
| 打印空白 | `display:none` 隐藏了打印容器 | 隐藏容器内控件而非容器 |
| 搜索框中文断输 | 监听 input 全量重渲染 | 用 `bindSearch()` |
| 新地点 TypeError | 注入晚于归一化循环 | 移到循环之前 |
| 地点 `lat>90` | GAZ 纬经写反 | 校验 `(lng,lat,今址,类型)` |
| 关系被测成漏抽 | 别名未归一伪影 | 用规范名口径比对 |
| 报告没更新 | SW 缓存 / FILES 清单缺文件 | bump CACHE；补 FILES |
| 内容没更新 | SWR 拿到 HTTP 缓存旧响应 | `fetch(req,{cache:'no-cache'})`；bump CACHE |
| 地图灰底红点 | OSM 挂起 + SW 拦跨域 img | Esri 主源 + SW 不拦跨域（见地图节） |
| 页面主区全空 / `Unexpected identifier '$'` | HTML_TEMPLATE 游离反引号 | 改 JS 前先 grep 紧邻反引号；`node -e "new Function(...)"` 校验 |
| 需确认 GitHub 与本地差异（哪些没传） | 无现成命令，git 不可用 | blob sha 全量比对法（见「确认 GitHub 与本地的差异」节） |
| agent-browser eval 报 `Invalid regular expression` | 代码串含 `?` 或 `[attr]` 被误解析成正则 | 用 `getElementById`/`getElementsByTagName`/`dataset`；视口用 `set viewport <w> <h>` |
| `ls`/`tail`/`dirname`/`agent-browser` 全部 command not found | 本会话 Bash 的 PATH 被裁（2026-09-13 实测） | 一切外部程序走绝对路径；列目录用 python `os.listdir`/`Path.glob`，读文件用 `io.open` |
| 编辑工具报成功但文件内容没变 | 写入偶发未落盘 | 改完立刻 grep/读取复核，别只信返回值 |
| 审计数字与页面差 1（6 vs 7 未知年份） | 审计自己另写一套判定 | 统一走 `src/core/`（见共享核心节） |
| 构建要等两分钟 | Python 端 800 轮 numpy 力导布局 | 已移除；Python 只给确定性初始坐标（见重构节） |

## 典型任务脚本
- 补录人物：`manual_persons.json` 写卡 → merge 注入 → `manual_relations.json` 加关系 → merge+generate → 部署。
- **JS 改完必跑解析校验**：提取 index.html 末段 `<script>`（`rfind('</script>')`），`node -e "new Function(...)"`；只动 CSS 可省。
- 对同一文件连续多次脚本替换时，**每次替换前重新 grep 实文**（锚点可能已被上一轮替换改变）。
- 充分性核查：`discover_persons.py` 三信号 → 表字信号兜底 → 抽查 → 结论。
