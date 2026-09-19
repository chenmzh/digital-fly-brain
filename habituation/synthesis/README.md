# 统一报告的重构与排版

主报告：**[habituation/report.pdf](../report.pdf)**；[阅读摘要](../REPORT.md)。

本目录保存统一报告的LaTeX源码。当前版本重写了学术表述，按背景与方法、重复刺激及状态干预、低维预测、经典特征补测、讨论和结论编排。H编号仅用于经典特征。实验数据和判据不变，三份分阶段PDF保持原样。

- `EDITORIAL_PLAN.md`：文字修订范围、科学内容保留项和验证要求。
- `report.tex`、`sections/`：重新组织的正文、附录和统一图表编号。
- `prepare_data.py`：标准库读取已有CSV/JSON，生成表格、曲线及数量汇总，不仿真、不拟合。
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

本报告为已有实验的事后综合，各项分析的前瞻、回顾或探索性质按实际设计顺序记录。结果描述模型神经响应，未验证真实行为机制。
