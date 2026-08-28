# 明朝那些事儿 · 五维知识图谱

基于《明朝那些事儿》（当年明月）全书抽取的结构化知识图谱与可视化报告。
覆盖 **156 章 / 7 部**，抽取出角色、地点、事件、关系、时间轴五类实体，并生成可交互的静态报告（角色卡 / 真实地图 / 时间线 / 章节打卡）。

> 🔴 **版权声明**：本书为受版权保护出版物，**本仓库不包含原著正文**（`明朝那些事儿.txt` 与含正文的 `chapters.json` 均未上传）。仓库内 `data/` 下所有 JSON 均为从原著抽取的**结构化事实数据**（人名、地名、事件、关系），仅供研究与学习使用。若需完整复现抽取流程，请自行准备合法取得的原著文本。

## 在线演示（GitHub Pages）

- 全七部报告：<https://CochraneK.github.io/ming/>
- 壹部专版：<https://CochraneK.github.io/ming/web/report_p1.html>

> 报告页面通过 CDN 加载 Leaflet 地图库与 OpenStreetMap 瓦片，需联网查看地图部分；其余内容（角色卡、时间线、章节打卡）已内联，离线可用。

## 仓库结构

```
src/                  抽取与生成流水线（Python）
  split_chapters.py   原著 txt → 章节切分（data/chapters.json，需自备原著）
  extract_auto.py     LLM 抽取章节 → extract_raw.json（依赖本地 OmniRoute 网关，可选）
  _dump_chapter.py    导出单章正文（供抽取使用）
  _append_extract.py  安全追加/覆写单章抽取结果
  merge.py            extract_raw.json → data.json（聚合+归一+挂地理标注）
  generate_report.py  data.json → web/report.html（静态报告生成器）
  clean_rules.py      人名/别名词典归一规则（generate_report.py 依赖）
data/                 派生数据（结构化事实，可自由使用）
  extract_raw.json    156 章原始抽取（角色/地点/事件/关系）
  data.json           merge 后的聚合数据（报告数据源）
  geo_annotations.json 地点地理标注（坐标/类型/现状）
  char_profiles.json  角色补充档案
  manual_relations.json 手工补的关系
  lifespans.json / reigns.json / voyages.json 生卒/在位/航行
  chapters_index.json 章节标题索引（已脱敏，仅标题无正文）
web/                  生成产物
  report.html         全七部交互报告（GitHub Pages 入口）
  report_p1.html      壹部专版
  index.html          着陆页（重定向到 report.html）
```

## 复现方式

### 最简：仅重建报告（无需原著）
直接用本仓库已发布的派生数据重建报告：

```bash
pip install -r requirements.txt   # 仅标准库即可，无需第三方包
python src/merge.py               # 由 data/ 重建 data.json（可选，已包含）
python src/generate_report.py     # 读取 data/data.json → 写出 web/report.html
```

### 完整：从原著重新抽取
1. 将你合法取得的《明朝那些事儿》全文保存为项目根目录 `明朝那些事儿.txt`。
2. 切分章节：`python src/split_chapters.py` → `data/chapters.json`。
3. 逐章抽取（需 LLM）：调用 `_dump_chapter.py` 取章节正文，经模型抽取五元组后由 `_append_extract.py` 写入 `data/extract_raw.json`。
4. 聚合：`python src/merge.py` → `data/data.json`。
5. 生成报告：`python src/generate_report.py` → `web/report.html`。

## 数据口径与限制

- 抽取以「事实结构化」为目标，角色卡含身份/势力/生卒/核心章节/重大事件/关系；地点含古今地名、坐标、遗迹类型与现状。
- 坐标与事件年份为草稿性质，以实地与权威史料为准。
- 后期章节（五~七部）由自动化抽取完成，密度可能低于前期，存在稀疏章节待补抽。

## 许可证

派生结构化数据以 CC BY 4.0 发布；原著名字与内容版权归原作者与出版社所有。
