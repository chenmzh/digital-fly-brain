# Habituation：连接组约束的记忆机制研究

研究JO-CE机械感觉输入引起的重复响应变化，以aBN1脉冲计数为主要观测量。实验包括固定连接与局部短时突触抑制的比较、状态干预、低维预测及经典特征补测。

**[统一总报告（语言修订版PDF）](report.pdf)** · [阅读摘要](REPORT.md) · [源码与修订说明](synthesis/README.md)。当前版本重写了正文表述，数据和判据不变。

本研究记录脑内神经响应，未模拟实际梳理动作。

## 导航

以下为保留的分阶段资料，不替代上面的统一阅读入口：

- **[分项：经典hallmarks补测](hallmarks/README.md)**：[525窗口结果与判定](hallmarks/REPORT.md)、[6页PDF](hallmarks/report.pdf)。部分恢复下H3有支持，H5方向一致；H4(b)未稳健建立，H6/H8未见效应，H7条件不足，H9/H10未测。
- **[阶段二：三轮研究闭环](stage2/README.md)**：因果状态干预、低维代理及新输入前瞻验证；[阶段报告PDF（历史）](stage2/report.pdf)、[文字结论](stage2/REPORT.md)。
- **[首轮论文式详细报告（历史PDF）](paper/report.pdf)**：24 页，含入门解释、中英文摘要、图表、参考文献及复现附录；[LaTeX 源码与编译说明](paper/README.md)。
- [研究方案](RESEARCH_PLAN.md)：假设、模型、预先规定的判据、停止条件。
- [文献与范式选择](LITERATURE.md)：经典 hallmarks、最小模型、抑制可塑性与候选感觉范式。
- [实验日志](LAB_NOTES.md)：pilot、运行中断、接续与所有方案偏离。
- [结果与结论](RESULTS.md)：实际结果、证据范围和下一步。
- [固定正式协议](protocols/main_v1.json)。
- [机器可读汇总](analysis/report.json)、[逐种子指标](analysis/metrics_by_seed.csv)、[训练曲线](analysis/training_responses.svg)。

## 首轮模型与数据

- M0 / `static`：原始 127,400 神经元全脑 LIF，保持固定连接。
- M1 / `std`：仅替换 JO-CE 的 4,764 条兴奋性输出连接，加入事件驱动资源变量；U=0.01，恢复时间常数 2 秒。不是生理拟合参数。
- 工程对照 / `std_zero`：U=0，验证与 M0 全脑脉冲等价。
- 70 个输入神经元；200 ms、150 Hz 等效离散随机驱动；序列内回放相同输入实现，5 个种子产生不同实现。
- 每序列 12 次刺激，起始间隔 0.5/2 秒；300 ms 响应窗口；训练后独立分叉休息 2/10 秒再探测。
- 同一序列不重置神经状态；跨独立条件恢复初态。

输入回放控制随机性，不代表 5 只不同动物。M1 是一个待批评、待比较的候选机制，不是认定的果蝇习惯化机制。

## 运行

使用项目已有 `.venv` 与固定上游，环境准备见[上级 README](../README.md)。从项目根目录执行，所有输出路径必须不存在；不需要新增依赖。

```bash
# 工程 pilot，含零 U 等价性及状态恢复重放检查
.venv/bin/python habituation/run_experiment.py \
  --pilot --output habituation/results/my_pilot

# 完整固定协议；单进程，可能超过 30 分钟，不宜放在过短的工具超时中
.venv/bin/python habituation/run_experiment.py \
  --output habituation/results/my_full_run

# 回读原始脉冲、校验数据与协议、重算指标；analysis 输出也必须是新路径
.venv/bin/python habituation/analyze.py \
  --runs habituation/results/my_full_run \
  --output habituation/results/my_analysis

# 快速单元测试，不运行全脑实验
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover \
  -s habituation -p 'test_*.py' -v
```

本机正式结果因一次工具超时分为三批，合并验证命令：

```bash
.venv/bin/python habituation/analyze.py \
  --runs habituation/results/main_v1 \
         habituation/results/continuation_a \
         habituation/results/continuation_b \
  --output habituation/results/reverified_analysis
```

不得仅运行 continuation 协议就声称完成主实验；分析器要求完整的 20 条序列。

## 文件与审计

- `run_experiment.py`：实际连续状态全脑仿真入口。
- `analyze.py`：独立回读与汇总；工程检查通过不代表生物假设阳性。
- `test_experiment.py`：协议、输入和指标测试。
- `protocols/`：主协议和仅用于执行接续的子集。
- `analysis/`：小型 CSV、JSON、SVG 汇总，适合版本管理。
- `results/`：本地原始全脑脉冲、输入实现、源文件快照、哈希与日志；沿用项目 Git 忽略规则。

恢复分支来自相同训练末态，因此原始分支文件只包含该分支的休息及探测事件，不重复保存共同训练前缀。CSV 使用秒单位时间；神经元 ID 在 Parquet 中为 int64，JSON 清单用字符串。

首轮没有进行参数拟合；阶段二对两个低维代理各拟合两个读出系数，但仍未拟合全脑生理参数。后续hallmarks补测没有拟合参数。上述研究计算阶段未修改上游、覆盖旧实验或自动提交/推送 GitHub。现按用户追加授权同步本目录的代码、汇总与报告；完整原始事件仍在本机，不随仓库上传。旧报告和审计记录中的“未提交/推送”描述的是当时状态，保留不改；详见[同步说明](../docs/PUBLICATION.md)。
