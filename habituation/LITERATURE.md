# 文献证据与实验选择

核对日期：2026-09-16。定向调研，不是系统综述。以下区分文献已报告的事实与本项目建议。

## 1. 习惯化并不是“响应随时间变小”

**Rankin et al. (2009), Habituation revisited**  
https://pmc.ncbi.nlm.nih.gov/articles/PMC2754195/  
DOI: 10.1016/j.nlm.2008.09.012（在线发表于 2008 年，期刊卷期为 2009 年）。

- 递减和自发恢复是基础特征，但刺激特异性、去习惯化、频率依赖恢复对于排除一般适应/疲劳很重要。
- 特征 4 不只有“刺激越频繁，递减越强”；还包括达到渐近水平后的频率依赖恢复。
- 新刺激 B 的反应与 B 后原刺激 A 的恢复是不同实验。后者还必须排除自然恢复与一般敏化。
- 单个系统不要求同时具有十项特征；但应说明实测了哪些，而不是只有下降曲线就声称全面复现。

**对本项目的约束**：使用相同输入，连续状态，独立恢复分支；报告神经输出代理，不将其直接称为动物行为学习。

## 2. 为什么要比较最小机制，而不是先训练全脑

**Smart, Shvartsman & Mönnigmann (2024), Minimal motifs for habituating systems**  
https://pmc.ncbi.nlm.nih.gov/articles/PMC11474051/  
DOI: 10.1073/pnas.2409330121。

- 记忆状态 `dx/dt = βu − αx` 加静态非线性读出即可表现反应递减、恢复和部分频率依赖。
- 直接乘随绝对时间衰减的包络是无效捷径：它没有正确的休息恢复，也没有生物学上特殊的时间零点。
- 该论文分析的单状态最小模型不满足完整的 H4(b)；串联不同时间尺度的单元可以扩展其能力。
- 这不是“所有含一个慢变量的全脑循环网络都必定不能满足 H4(b)”的定理。复杂网络、其他状态和非单调读出需要另行分析。

**对本项目的约束**：M0/M1 的目的不是证明 STD 是全新机制，而是建立可被恢复/干预实验否定的连接组基线。完整图谱的贡献尚需简单模型及图结构对照。

## 3. 为什么首轮选择触角机械感觉

**Shiu et al. (2024), A Drosophila computational brain model reveals sensorimotor processing**  
https://www.nature.com/articles/s41586-024-07763-9

Figure 5 与对应正文：

- JON → aBN1/aBN2 → aDN1/aDN2 为已研究的触角梳理相关回路。
- JO-CE 刺激能激活 aBN1；模型的这一预测得到钙成像验证。
- JO-F 虽与 aBN1 有直接连接，却不能可靠激活它。模型提出抑制性回路解释，去除相关抑制的预测仍有未验证部分。
- **论文没有在这里证明 JO-CE → aBN1 的习惯化机制。**

本项目从固定上游 Notebook 抽取 70 个 JO-CE ID；aBN1、aDN1、aDN2 ID 均在 v630 表中核对。我们不把论文图示/概括中的神经元数直接代替实际输入清单。

选择理由是“正常传递有依据、接口明确、可以立即提出可证伪的记忆问题”，而不是认为它比所有嗅觉/视觉范式更重要。它适合第一轮模型机制实验，不是现成的完整习惯化行为范式。

## 4. 真正的生物机制竞争者：抑制可塑性与去抑制

**Das et al. (2011), Plasticity of local GABAergic interneurons drives olfactory habituation**  
https://pmc.ncbi.nlm.nih.gov/articles/PMC3169145/  
DOI: 10.1073/pnas.1106411108。

- 果蝇对 CO₂/ethyl butyrate 暴露 30 分钟后出现有气味选择性的短期行为习惯化；论文报告恢复半衰期约 20 分钟。
- 遗传、生理及解剖证据支持触角叶局部抑制性传递增强，涉及 LN、PN、rut/cAMP、GABA 及 NMDA 相关机制。
- 存在更长时间尺度的过程，不能用本轮 2 秒资源恢复常数声称原样复现。

**Paranjpe et al. (2012), Gustatory habituation in Drosophila relies on rutabaga (adenylate cyclase)-dependent plasticity of GABAergic inhibitory neurons**  
https://doi.org/10.1101/lm.026641.112

**Trisal et al. (2022), A Drosophila Circuit for Habituation Override**  
https://pmc.ncbi.nlm.nih.gov/articles/PMC8985855/  
DOI: 10.1523/JNEUROSCI.1842-21.2022。

- 足部糖刺激约 10 分钟导致 PER 递减；不同感觉刺激或相关神经元激活可使原糖反应恢复。
- 论文用初始反应的低浓度测试排除简单天花板掩盖的敏化；不是仅看强糖条件下“不再更强”。
- 证据支持多巴胺相关细胞经直接或间接方式减弱抑制、解除习惯化的模型；不能把全部中间连接都写成已完整确定。
- 足部输入与已有工程基线的唇瓣输入不同。

**对本项目的建议**：下一轮比较 STD、慢抑制增强、抑制＋去抑制，而不是事先指定 STD 为最终答案。若转向嗅觉，应重做细胞标注/时间尺度匹配，不能仅换一组随机感觉 ID。

## 5. 视觉惊跳与个体模型

**Engel & Wu (2009), Neurogenetic approaches to habituation and dishabituation in Drosophila**  
https://pmc.ncbi.nlm.nih.gov/articles/PMC2730516/  
DOI: 10.1016/j.nlm.2008.08.003。

**Boon et al. (2026), Dynamical modeling of individual sensory reactivity and habituation learning**  
https://pmc.ncbi.nlm.nih.gov/articles/PMC13037877/  
DOI: 10.1073/pnas.2524738123。

light-off 跳跃是适合对照经典行为特征的路线；近期工作已对个体感觉反应和习惯化建立动力学/统计模型。**light-off ≠ looming ≠ 任意视觉神经元激活**，不能把脑内任意下降读出当作同一范式。

在本项目开展前还需要：准确视觉编码、跳跃相关输出及腹神经索覆盖检查、与二值行为反应匹配的读出。这些未完成，所以本轮不冒充视觉习惯化复现。

## 6. 最值得继续的研究问题

> 哪些刺激与干预能够区分“局部资源耗竭”“抑制增强”“多时间尺度隐状态”？真实连接组是否提高留出预测能力，而不只是增加模型规模？

优先顺序：

1. 先确认基线能否跨次保持反应、扩展模型是否出现慢状态效应。
2. 恢复分支加密，报告末态深度、绝对响应、相对初始响应及已损失响应的恢复比例，避免仅凭一种归一化定义“恢复更快”。
3. 用独立激活验证输出通路仍然可用；引入新刺激和时间匹配的 A→B→A / A→休息→A / 未训练→B→A。
4. 用抑制回路干预区分竞争机制，拟合部分协议、预测留出协议。
5. 最后比较最小模型、局部子图、匹配随机图谱与全图，判断真实结构的必要性。

本轮只完成第 1 项及第 2 项的两个稀疏探测时间点，不声称完成后面的机制鉴别。
