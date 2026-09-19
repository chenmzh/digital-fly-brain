# 习惯化研究：LaTeX 学术报告

## 交付

- **[PDF：report.pdf](report.pdf)**：24 页，约 1.4 万中文字，4 幅矢量图、9 张表、10 篇参考文献。
- **[完整排版源码包：report_source.zip](report_source.zip)**：包含 LaTeX、BibTeX、绘图数据、制表脚本、校验记录及所需的小型分析汇总；不包含编译器、缓存、上游图谱或原始脉冲数据。
- [LaTeX 主文件](report.tex)、[参考文献](references.bib)、[PDF 校验记录](validation_report.json)。

论文标题：**连接组约束的果蝇全脑模型中习惯化样神经响应的最小慢机制——固定连接与局部短时突触抑制的可重复计算比较**。

按通用学术论文/预印本体例排版，不冒用某个期刊的正式版式。包含中英文摘要、通俗摘要、背景、方法、结果、讨论、局限、未来实验、透明性声明和附录。没有虚构作者、单位、资助、同行评审或发表状态；正式署名需要修改 `report.tex` 中的 `\ReportAuthor` 并经作者确认。

## 面向非专业读者的设计

- 从神经元、突触、连接组讲起，区分结构、参数与动态状态。
- 用“读者导读”解释时间常数、突触资源和递减百分数的分母。
- 明确区分短时突触效能下降与抑制性神经元作用。
- 使用刺激/状态分支示意图、训练响应图、恢复点图、配对间隔比较图。
- 附术语表、逐种子数据、简单解析推导与常见误读。
- 持续区分文献事实、本项目实测、机制解释及未执行的建议。

## 数据与证据

本次没有新增神经仿真或拟合参数。重新运行原始事件分析后，结果对象与现有 `../analysis/report.json` 完全一致；报告数据对应 20 条序列、280 个窗口和 60 个原始事件文件。

`prepare_data.py` 使用 Python 标准库读取：

- `../analysis/responses.csv`
- `../analysis/metrics_by_seed.csv`
- `../analysis/report.json`
- `../protocols/main_v1.json`

主表数值逐种子重算后与审计结果核对，再生成 `data/` 中的表格行和绘图 CSV。`data_manifest.json` 记录科学输入与派生数据哈希；`build_manifest.json` 记录排版源码与 PDF 哈希。

**源码包是排版复现包，不是完整科学数据归档。** 它包含上述小型分析文件，能够重建图表与报告；从原始事件重新验证实验仍需项目本机的 `habituation/results/` 和固定上游数据。

## 重编译

从项目根目录执行：

```bash
# 本机已经具备此便携编译器；首次新机器安装时才需要执行
python3 habituation/paper/setup_tex.py

# 重建图表数据并编译 LaTeX，不运行神经仿真
bash habituation/paper/build.sh

# 检查 PDF、文字、引用、字体嵌入、数据和源码哈希
python3 habituation/paper/validate_report.py
```

源码包解压后保留 `habituation/paper/`、`habituation/analysis/` 和 `habituation/protocols/` 相对位置，可使用同样命令。

### 编译依赖

- Python 3 标准库；制表不需要增加 NumPy、Pandas 或 Matplotlib。
- Tectonic 0.17.0（XeTeX/LaTeX 工具链）。`setup_tex.py` 只为 Linux x86_64 下载经过 SHA-256 校验的官方便携二进制，不使用 sudo 或修改系统包。
- 系统字体：`Noto Serif CJK SC`、`Noto Sans CJK SC`、`Noto Sans Mono CJK SC`。
- 首次编译需要联网下载 TeX 宏包，随后使用本地缓存。
- PDF 校验使用 Poppler 的 `pdfinfo`、`pdftotext` 和 `pdffonts`；这些工具不是神经仿真依赖。

其他平台可安装适用的 Tectonic 并设置绝对路径：

```bash
TECTONIC_BIN=/absolute/path/to/tectonic bash habituation/paper/build.sh
```

编译器位于 `.tools/`，TeX 缓存位于 `.cache/`（或外部 `XDG_CACHE_HOME`），中间文件和日志位于 `_build/`；三者均忽略提交。只有最终 `report.pdf` 与排版材料是交付文件。

Tectonic 会提示使用了系统 Noto 字体的绝对路径；这是跨机器重现性提示。PDF 已嵌入字体，阅读时不要求接收者安装这些字体。重新编译时需要对应字体；不承诺不同机器、字体版本或构建时间生成字节完全相同的 PDF。

## 实际检查结果

- 原始事件重新分析与旧报告一致；主表数值独立重算一致。
- 24 页均可提取文字；关键数值及完整协议 SHA-256 与审计结果一致。
- 10 个参考文献条目、图表及交叉引用已解析。
- 没有溢出版心的 `Overfull` 警告、缺字或 PDF 链接注释错误。
- PDF 使用的字体全部嵌入。
- 已渲染全部页面缩略图，并查看标题页、实验示意图和结果图表；修正了初版示意图文字重叠。

自动校验不代替科学审稿，也不声称可以自动判断图形是否美观。报告保留研究局限：神经读出不是行为、M1 首次输出受损、恢复点稀疏、缺少机制竞争和结构对照。

本次只创建本地报告及源码包，没有投稿、发布或推送 GitHub。
