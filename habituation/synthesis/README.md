# 统一报告的重构与排版

主报告：**[habituation/report.pdf](../report.pdf)**；[阅读摘要](../REPORT.md)。

本目录不是三份PDF的拼接工具，而是重新写作的统一稿：一份背景/共同方法，Q1–Q5串联现象充分性、因果归因、预测压缩、经典特征和结构价值；H编号只指经典特征。旧“未来工作”按实际进展更新，三份历史PDF和已记录的科学结果不修改。

- `EDITORIAL_PLAN.md`：论证链、去重与旧认识更新清单。
- `report.tex`、`sections/`：重新组织的正文、附录和统一图表编号。
- `prepare_data.py`：标准库读取既有审计CSV/JSON，重新生成表格、曲线和数量账本，不仿真、不拟合。
- `data_manifest.json`：输入和生成数据的SHA-256。
- `preserved_sources.json`：重构前167个已跟踪历史文件的字节保护清单。
- `build_manifest.json`：本次排版源码、编译器和总PDF哈希。
- `validate.py`、`validation.json`：数值、哈希、数量、引用、书签、字体和版面检查。
- `VALIDATION.md`：最终PDF指纹、全页渲染及科学表述人工复核记录。

## 重建

从项目根目录执行：

```bash
bash habituation/synthesis/build.sh
python3 habituation/synthesis/validate.py
```

只读已发布汇总，不需要原始事件，也不会运行神经实验。依赖系统Python标准库、既有便携Tectonic及Noto CJK字体；复用首轮 `paper/.tools/tectonic` 和 `paper/.cache/`。编译器尚未准备时，按 [首轮排版说明](../paper/README.md) 安装，不修改神经仿真环境。结构/文本验证还使用 `qpdf`、`pdfinfo`、`pdftotext`、`pdffonts`。

中间文件在忽略目录 `.build/`；发布PDF在上级 `habituation/report.pdf`。可通过 `TECTONIC_BIN` 指定已有编译器。初次排版可能需要下载宏包；不承诺不同字体/编译器环境下PDF字节一致。

## 数量与解释

280+90+111+525=1006个正式观测窗口，其中6个空白检查窗。1212是此前已审计的事件文件数量，不是本次新增样本；后期文件包含单独保存的静默段。60个拟合、80个回顾性窗口复用旧数据，102个冻结预测与102个实际M1窗口配对，不重复计数。11个种子标识属于同一图谱，不是11只动物。

本综合写作是事后重构，各次实验的前瞻/回顾/探索身份保留。不得把最终连贯叙事倒写成整套实验一开始就已完整预注册。模型的部分特征支持不等于真实机制、完整行为或意识证据。
