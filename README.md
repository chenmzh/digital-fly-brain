# 数字果蝇：全脑基线与习惯化机制研究

基于 Shiu 等（Nature, 2024）的官方 Brian2 实现，先复现全脑神经活动，再研究连接组约束的动态机制。**本项目不是完整数字动物，不包含虚拟身体。** 原始基线没有可塑性；新增习惯化研究比较固定连接与局部短时突触抑制。

> **[统一研究报告（语言修订版PDF）](habituation/report.pdf)** · [阅读摘要](habituation/REPORT.md) · [源码与修订说明](habituation/synthesis/README.md)
>
> 报告包括模型与方法、重复刺激实验、状态干预、低维预测和经典特征补测。当前版本重写了正文表述，实验数据和结论不变，三份历史报告保留。

- 总体计划：[PLAN.md](PLAN.md)
- 本机复现结果与限制：[docs/REPRODUCTION.md](docs/REPRODUCTION.md)
- 习惯化研究、文献和全脑实验：[habituation/README.md](habituation/README.md)
- 分项资料：经典特征补测：[结果](habituation/hallmarks/REPORT.md)、[6页PDF](habituation/hallmarks/report.pdf)。
- 模型论文：https://www.nature.com/articles/s41586-024-07763-9

## 已完成

固定 FlyWire v630，127,400 个神经元、14,687,178 条有向连接，代表 52,793,639 个解剖突触；没有裁剪子图。

单进程，积分步长 0.1 ms，每条件 3 次、每次 1 秒：

| 条件 | MN9 各次放电率（Hz） | 均值（Hz） |
|---|---|---:|
| 无输入 | 0 / 0 / 0 | 0 |
| 糖 GRN 100 Hz | 71 / 69 / 63 | 67.67 |
| 糖 100 Hz＋苦味 GRN 100 Hz | 7 / 6 / 7 | 6.67 |

同种子独立复跑的全部脉冲记录和 Parquet 文件 SHA-256 一致。完整三条件实验耗时约 272 秒，进程峰值 RSS 约 2.76 GiB；包含加载、建模、可能的代码编译、计算和写盘，不能当作纯仿真吞吐率。

这是**小样本定性复现**，不是原论文 30 次重复、164 项预测或全部图表的完整复现。

## 公开仓库与本地文件

公开版本包含基线与习惯化实验代码、依赖清单、研究方案、汇总 CSV/JSON、统一总报告与三份历史 PDF 及排版源码；首轮还提供排版源码 ZIP。不包含 `.venv/`、`upstream/`、任何层级的 `results/`、工具/字体缓存和原始运行日志。汇总结果可直接查看，但全脑原始事件仍保留在本机；新机器需准备环境与上游数据，重新运行实验才能独立回读原始事件。同步范围与历史状态说明见 [docs/PUBLICATION.md](docs/PUBLICATION.md)。

本项目是独立复现工作，不是原作者官方实现的替代或背书。上游仓库使用 MIT 许可证；其版权声明保留在独立检出的仓库中。

## 在当前机器上再运行

环境已创建在 `.venv/`。从项目根目录执行，无需激活环境：

```bash
.venv/bin/python scripts/reproduce.py --output results/my_first_run --trials 3
```

输出目录必须是新路径，不会覆盖已有实验。脚本强制单进程，限制 BLAS/OpenMP 原生线程，使用 Cython 后端；保留原作者模型源码和生理参数，仅设置实验输入、运行时长、随机种子等。

只做一个短时糖刺激 smoke test：

```bash
.venv/bin/python scripts/reproduce.py \
  --output results/my_smoke --conditions sugar --duration-ms 100 --trials 1
```

增加至作者通常使用的 30 次重复（更耗时，但仍只是这三个条件，不是整篇论文）：

```bash
.venv/bin/python scripts/reproduce.py --output results/my_30_trials --trials 30
```

固定种子独立复跑，并校验完整三条件结果：

```bash
.venv/bin/python scripts/reproduce.py \
  --output results/my_repeat --conditions sugar --duration-ms 1000 --trials 1
.venv/bin/python scripts/verify_results.py results/my_first_run --repeat results/my_repeat
```

默认种子从 1701 开始，每次试验递增。跨平台、不同编译器或库版本不保证位级一致。

## 在新环境重新准备

当前目录已经准备好，不要重复克隆到已有路径。新副本可依次执行：

```bash
git clone https://github.com/philshiu/Drosophila_brain_model.git upstream/Drosophila_brain_model
git -C upstream/Drosophila_brain_model checkout --detach 91bdd1e7dcf193f3e7ca5a8933497fcef63b7960
uv venv --python 3.10.21 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip check --python .venv/bin/python
```

需要可用的 C/C++ 编译器。数值与仿真依赖按上游 `environment_full.yml` 固定；该文件原本为 Windows/Conda 环境，这里使用 Linux/uv 适配。PyArrow 从原始 11.0.0 升至 17.0.0，以解决本机退出崩溃；详见复现记录。无需 GPU、无需下载电镜图像，也未安装或启动 Jupyter 服务。

## 结果文件

`results/baseline_v630/` 包含：

- `manifest.json`：状态、提交、参数、依赖、资源、数据和源码 SHA-256。
- `runner_snapshot.py`：该次运行入口的源码快照；回放请使用项目 `scripts/reproduce.py`，快照用于审计。
- `inputs.json`：从作者 Notebook 提取的感觉神经元和 MN9 ID，JSON 使用字符串避免整数精度丢失。
- `*_trial*.parquet`：每次实验全部活跃细胞的脉冲，字段为秒单位时间 `t`、试验 `trial`、整型 `flywire_id` 和条件 `exp_name`。静默细胞不产生记录；完整细胞表仍在上游数据中。
- `trials.csv`：逐次脉冲数、活跃细胞数、MN9 频率、耗时与数据哈希。
- `summary.json`：条件汇总与定性验收。
- `reference.json`：作者仓库中原始糖刺激结果的统计，仅用于参考。
- `verification.json`：独立回读、重算统计和确定性复跑校验。

标准输出日志位于 `results/*.log`；依赖快照位于 `docs/environment.freeze.txt`。仿真结果不应与原始生物实验数据混为一谈。

## 习惯化研究进展与下一步

[统一总报告](habituation/report.pdf)汇总以下实验：

1. **重复刺激**：[首轮](habituation/RESULTS.md)的固定连接模型未见递减，局部短时突触抑制产生递减与恢复，但初次传递下降和下游地板问题保留。
2. **状态干预与预测**：[阶段二](habituation/stage2/README.md)完成资源/快状态干预、旁路及低维代理的新输入前瞻检验，共201个正式窗口。代理拟合读出系数，未训练全脑参数。
3. **经典特征补测**：[hallmarks补测](habituation/hallmarks/README.md)增加525个观测窗口。部分恢复H3与人工输入率H5有支持；H4(b)未稳健建立，H6和本次两种B的H8未见效应，H7资格不足，H9/H10未测。

三阶段合计1006个观测窗口（含6个空白检查窗），不是1006个独立动物样本。本次统一写作未新增神经实验或拟合。尚未完成局部/随机图对照、真实行为验证、Flyvis复现、MaleCNS迁移或身体闭环；反弹的时序/结构来源与长期机制仍待检验。
