# 数字果蝇：全脑复现基线

基于 Shiu 等（Nature, 2024）的官方 Brian2 实现，先复现全脑神经活动，再探索连接组约束的参数训练。**本项目不是完整数字动物，不包含虚拟身体或学习机制。**

- 总体计划：[PLAN.md](PLAN.md)
- 本机复现结果与限制：[docs/REPRODUCTION.md](docs/REPRODUCTION.md)
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

公开版本包含实验入口、依赖清单、计划及复现报告；不包含 `.venv/`、`upstream/`、`results/` 和原始崩溃日志。上述实测结果为本机实验记录，不是随公开仓库附带的数据文件。新机器请先按下文准备环境与上游数据，再运行生成自己的结果。

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

## 下一步

建议先扩大相同协议的重复次数与刺激频率覆盖，再设计参数敏感性实验；尚未开展参数训练、Flyvis 复现、MaleCNS 迁移或身体闭环。
