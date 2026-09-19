# 经典 habituation hallmarks 补测

目标是在已有完整M1中实际检验可测试的经典特征，而不是修改机制直到全部通过。原模型、原实验和两版报告不变。

## 方案与范围

- [主方案](PROTOCOL.md)、[固定数值协议](protocol.json)、[运行前SHA-256](frozen_before_runs.sha256)。
- [恢复指标解释补充](RECOVERY_INTERPRETATION.md)：在主实验启动前固定，同时看已损失响应比例和首次响应比例。
- [H3部分恢复补充](H3_PARTIAL_RECOVERY.md)：文献允许部分恢复，故另测试2秒休息；原10秒结果与较严格判据保留。
- [H4(b)资格补测](FREQUENCY_SUPPLEMENT.md)：原比较两例未满足门槛，另测T=0.75秒、24次；不改原阈值，保留原结果，完成这一组即停止扩大。
- 全脑单进程；种子3701–3703；不拟合、不改变U/tau、不人工恢复资源。
- H7需要B有可比较的aBN1初始响应；H8不需要B自身引起aBN1，但要求B有效激活其他神经元并排除残留输出。
- H9只有先可靠诱发去习惯化才有基础；H10不以秒级实验冒充长期检验。

## 执行命令

从项目根目录使用已有 `.venv`。输出目录必须不存在；前三部分顺序执行。资格补测还引用保留的 `analysis/full/report.json` 来源哈希，不能把任意新主分析冒充本轮历史设计证据。不并发跑全脑仿真。

```bash
.venv/bin/python habituation/hallmarks/run.py \
  --part novel --output habituation/hallmarks/results/my_novel
.venv/bin/python habituation/hallmarks/run.py \
  --part main --output habituation/hallmarks/results/my_main
.venv/bin/python habituation/hallmarks/run_partial.py \
  --output habituation/hallmarks/results/my_partial
```

独立回读实际原始事件，而不只读取运行器计数：

```bash
.venv/bin/python habituation/hallmarks/analyze.py \
  --novel habituation/hallmarks/results/novel_v1 \
  --main habituation/hallmarks/results/main_v1 \
  --partial habituation/hallmarks/results/partial_v1 \
  --frequency habituation/hallmarks/results/frequency_v1 \
  --output habituation/hallmarks/results/new_audit

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover \
  -s habituation/hallmarks -p 'test_*.py' -v
```

资格补测的执行入口是 `.venv/bin/python habituation/hallmarks/run_frequency.py --output habituation/hallmarks/results/my_frequency`。

分析器可只接收某一完整实验（资格补测还必须提供主实验对照），但那不是整个补测已完成。完整审计核对刺激/静默窗口覆盖、时间表、事件哈希、整数ID、实际感觉脉冲、恢复边界、首次训练的跨程序事件等价以及预先规定的筛查。仅有局部均值变化不能证明完整hallmark。

## 文件格式与复核边界

- `results/*/intervals.csv`：包含刺激读出和全部静默间隔；`responses.csv`为300ms读出窗口子集。`fast24`训练行只存额外的第13–24次，其前缀是`fast12`；主实验H3第一轮也复用该前缀，分析器明确拼接，不把分叉当作独立样本。
- `events_*.parquet`：每个窗口的完整全脑事件；`tick`是相对该窗口起点的0.1ms整数时间格，`flywire_id`为int64。
- `pattern_*.npz`：冻结的命令输入；命令事件不直接等于实际感觉脉冲。
- `runner_snapshot.py`、`entrypoint_snapshot.py`（补充入口）、`manifest.json`：代码与数据来源、完成状态和资源记录。
- `analysis/`：小型汇总，适合版本管理。原始事件仍被Git忽略。

## 报告构建

含资格补测的最终审计保存到 `analysis/final/` 后（`analysis/full/`是此前主分析，保留不覆盖）：

```bash
bash habituation/hallmarks/build_report.sh
python3 habituation/hallmarks/validate_report.py
```

生成 `REPORT.md`、`report_data/`、`report.pdf` 及源码/数据哈希。复用第一版报告的便携Tectonic和字体缓存，不执行新仿真；如编译器尚未安装，先按 `habituation/paper/README.md` 准备。系统Fontconfig兼容性警告不应与缺字、溢出或未解析引用混同，PDF另行验证。

3个种子不是3只动物。筛查阈值是本项目的效应量约定，不是经典文献规定的统一数值，也不是显著性检验。实际完成情况与结论以最终审计和报告为准，不将待运行项目写成阳性。
