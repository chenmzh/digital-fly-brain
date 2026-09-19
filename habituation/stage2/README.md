# Habituation 阶段二：三轮研究闭环

- **[阶段报告 PDF](report.pdf)**：因果状态干预、低维代理、冻结预测的新输入验证。
- **[文字版结论](REPORT.md)**：主要结果、科学边界与证据入口。
- [预先冻结的阶段方案](PROTOCOL.md)、[循环日志与工程偏离](LOOP_LOG.md)。
- [代理规格](cycle2_spec.json)、[新条件运行前实施声明](cycle3_implementation.md)。
- [循环一审计](analysis/cycle1/report.json)、[冻结预测](analysis/cycle2/prospective_predictions.csv)、[前瞻误差](analysis/cycle3/scores_by_condition.csv)。

## 实际完成

1. **模型内因果干预**：5个输入实现、90个窗口。恢复资源使aBN1均值从0.4回到8.2，清除快状态无救援；双重恢复与初次全脑事件一致，旁路训练前后全事件一致。
2. **两个低维代理**：只用旧短间隔60个窗口，各拟合两个非负读出系数。其他80个旧窗口仅作为回顾性检查。
3. **前瞻验证**：18个候选中按预测分歧选两个新协议，并加新种子对照。102个M1预测窗口在新全脑运行前冻结，另加9个M0初态窗口。资源代理通过3/3协议的MAE门槛，积累代理仅1/3。

共新增201个正式响应窗口，回读126个原始事件文件。强刺激出现2/1/1脉冲的局部反弹，作为**事后探索性诊断**记录，不混入预设评分。这些都是指定模拟器中的结果，未确定活体机制或连接组相对所有简单模型的独特优势。

## 运行与独立复核

从项目根目录运行；使用原 `.venv` 和固定上游，不新增仿真依赖。所有实验与审计输出必须是不存在的新路径。

```bash
# 重新运行第一循环（默认五个旧种子）
.venv/bin/python habituation/stage2/run_cycle1.py \
  --output habituation/stage2/results/my_cycle1

# 审计本次已完成的第一循环，不包含失败目录
.venv/bin/python habituation/stage2/analyze_cycle1.py \
  --runs habituation/stage2/results/cycle1_s1701_fixed \
         habituation/stage2/results/cycle1_remaining \
  --output habituation/stage2/results/my_cycle1_audit

# 重新拟合并另存预测；不会执行全脑仿真
.venv/bin/python habituation/stage2/surrogates.py \
  --output habituation/stage2/results/my_surrogates

# 原冻结预测下的第三循环：逐条件执行，不要并发启动重型仿真
for condition in new_seed_control f200_p400_gap800 f150_p400_gap800; do
  .venv/bin/python habituation/stage2/run_cycle3.py \
    --condition "$condition" \
    --output "habituation/stage2/results/my_${condition}"
done

# 审计本次已完成的全部前瞻条件
.venv/bin/python habituation/stage2/analyze_cycle3.py \
  --runs habituation/stage2/results/cycle3_new_seed_control \
         habituation/stage2/results/cycle3_f200_p400_gap800 \
         habituation/stage2/results/cycle3_f150_p400_gap800 \
  --output habituation/stage2/results/my_cycle3_audit

# 快速单元测试，不运行全脑网络
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover \
  -s habituation/stage2 -p 'test_*.py' -v
```

`run_cycle3.py` 默认使用 `analysis/cycle2/frozen_models.json`，检查来源及预测哈希。新拟合文件可以通过 `--frozen` 另行指定，但不能冒充本报告的原冻结版本。`analyze_cycle3.py` 有意按本报告的固定预测评分，不是任意数据集的通用分析器。

## 报告构建

```bash
# 编译器已安装时无需重复setup；使用第一版报告的便携Tectonic
python3 habituation/paper/setup_tex.py
bash habituation/stage2/build_report.sh
python3 habituation/stage2/validate_report.py
```

- `make_report.py` 从已审计的CSV/JSON生成文字报告、图表数据与阶段摘要；不会再拟合或执行神经仿真。
- `report.tex`、`figures.tex`、`references.bib` 是LaTeX源文件；`report_build_manifest.json` 记录PDF及源文件哈希。
- 编译沿用便携Tectonic 0.17.0、Noto CJK字体和已有宏包缓存；读PDF不需要安装字体。首次获取缺失宏包可能需要联网。
- 本机Fontconfig配置与便携编译器之间会产生非阻断的配置兼容提示；不得将它们与缺字、未解析引用或版心溢出混为一谈。PDF文本和嵌入字体另行检查。
- `.paper_build/` 只存排版中间产物；`results/` 的原始事件继续被Git忽略。本目录没有自动提交或推送。

第一版24页报告仍在 [../paper/report.pdf](../paper/report.pdf)，未被本阶段覆盖。下一轮的H4只是已提出的待检验假设，不是已经完成的新实验。
