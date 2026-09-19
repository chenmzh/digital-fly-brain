#!/usr/bin/env python3
"""Generate stage-report tables and narrative from completed, audited cycles."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_experiment as base
pd,np=base.pd,base.np
HERE=Path(__file__).resolve().parent


def main():
    c1=json.loads((HERE/'analysis/cycle1/report.json').read_text())
    c2=json.loads((HERE/'analysis/cycle2/frozen_models.json').read_text())
    c3=json.loads((HERE/'analysis/cycle3/report.json').read_text())
    one=pd.read_csv(HERE/'analysis/cycle1/responses.csv')
    three=pd.read_csv(HERE/'analysis/cycle3/forecast_outcomes.csv')
    all_three=pd.read_csv(HERE/'analysis/cycle3/responses.csv')
    data=HERE/'report_data';data.mkdir(exist_ok=True)
    models=['resource','accumulator'];names={'resource':'资源代理 S','accumulator':'积累代理 I'}
    conditions=c2['selected_conditions'];labels={conditions[0]['name']:'新种子对照',conditions[1]['name']:'判别 A',conditions[2]['name']:'判别 B'}
    scores=pd.DataFrame(c3['scores'])
    relative=all(scores[(scores.condition==c['name'])&(scores.surrogate=='resource')].mae.iloc[0] < scores[(scores.condition==c['name'])&(scores.surrogate=='accumulator')].mae.iloc[0] and scores[(scores.condition==c['name'])&(scores.surrogate=='resource')].rmse.iloc[0] < scores[(scores.condition==c['name'])&(scores.surrogate=='accumulator')].rmse.iloc[0] for c in conditions[1:])
    spass=int(scores[scores.surrogate=='resource'].mae_screen.sum());ipass=int(scores[scores.surrogate=='accumulator'].mae_screen.sum())
    relative_text='两个判别协议均支持资源代理误差更小的排序预测' if relative else '两个判别协议未一致支持资源代理误差更小的排序预测'
    absolute_text='资源代理在三个协议均达到预设精度门槛，但这仅限本次测试范围' if spass==3 else '资源代理未在所有协议达到预设精度门槛，因此“现有低维近似可可靠外推”的强版本未获支持'
    future=('下一假设 H4：在已测范围内，单一资源状态加简化读出可能已足够预测粗粒度输出；应以新的刺激时序、跨通路输入与结构对照主动寻找其失效边界，而非继续重复成功条件。'
            if spass==3 else '下一假设 H4：平均输入/平均资源加线性阈值读出遗漏了脉冲内时序、空间权重或网络非线性；应先拆分这些近似，再用另一组从未观察的新协议测试，不能在本次测试集重拟合后宣称外推成功。')
    metric_rows=[]
    for c in conditions:
        for model in models:
            r=next(x for x in c3['scores'] if x['condition']==c['name'] and x['surrogate']==model)
            metric_rows.append(f"{labels[c['name']]} & {names[model]} & {r['n']} & {r['mae']:.3f} & {r['rmse']:.3f} & {'是' if r['mae_screen'] else '否'}"+r" \\")
    (data/'forecast_scores.tex').write_text('\n'.join(metric_rows)+'\n')
    fit_rows=[]
    for model in models:
        m=c2['models'][model]
        fit_rows.append(f"{names[model]} & {m['A']:.4f} & {m['B']:.4f} & {m['fit_metrics']['rmse']:.3f} & {m['retrospective_metrics']['rmse']:.3f}"+r" \\")
    (data/'fit_scores.tex').write_text('\n'.join(fit_rows)+'\n')
    rebounds=[r for r in c3['exploratory_rebounds'] if r['max_upward_step']>0]
    rebound_rows=[f"{r['seed']} & ${r['from_stimulus']}\\to {r['to_stimulus']}$ & ${r['response_before']}\\to {r['response_after']}$ & {r['resource_state_change']:.6f} & {r['resource_prediction_change']:.3f}"+r" \\" for r in rebounds]
    (data/'rebounds.tex').write_text('\n'.join(rebound_rows)+'\n')
    interventions=[]
    phases=[('initial','初次'),('sham','训练后'),('fast_reset','清快状态'),('resource_reset','恢复资源'),('both_reset','两者恢复')]
    for index,(phase,label) in enumerate(phases):
        values=one[(one.phase=='train')&(one.pulse==0)].aBN1 if phase=='initial' else one[one.phase==phase].aBN1
        interventions.append({'x':index,'mean':values.mean(),'minus':values.mean()-values.min(),'plus':values.max()-values.mean()})
    pd.DataFrame(interventions).to_csv(data/'causal.csv',index=False)
    baseline_rows=[];curve_rows=[]
    for i,c in enumerate(conditions):
        selected=three[three.condition==c['name']]
        train=selected[selected.phase=='train'].groupby('pulse').agg(actual=('aBN1','mean'),low=('aBN1','min'),high=('aBN1','max'),resource=('resource','mean'),accumulator=('accumulator','mean')).reset_index()
        train['trial']=train.pulse+1;train.to_csv(data/f'train_{i}.csv',index=False)
        recovery=selected[selected.phase=='recovery'].groupby('rest_ms').agg(actual=('aBN1','mean'),low=('aBN1','min'),high=('aBN1','max'),resource=('resource','mean'),accumulator=('accumulator','mean')).reset_index()
        recovery['rest_s']=recovery.rest_ms/1000;recovery['minus']=recovery.actual-recovery.low;recovery['plus']=recovery.high-recovery.actual
        recovery.to_csv(data/f'recovery_{i}.csv',index=False)
        first=float(train.actual.iloc[0]);late=float(train.actual.tail(3).mean());static=float(all_three[(all_three.condition==c['name'])&(all_three.model=='static')].aBN1.mean())
        baseline_rows.append(f"{labels[c['name']]} & {c['input_hz']:g} & {c['pulse_ms']:g} & {c['interval_ms']/1000:g} & {static:.2f} & {first:.2f} & {late:.2f}"+r" \\")
        curve_rows.append({'condition':labels[c['name']],'static_initial':static,'std_initial':first,'std_late':late,'probe_1s':float(recovery[recovery.rest_ms==1000].actual.iloc[0]),'probe_5s':float(recovery[recovery.rest_ms==5000].actual.iloc[0])})
    (data/'baselines.tex').write_text('\n'.join(baseline_rows)+'\n')
    pd.DataFrame(curve_rows).to_csv(data/'neural_summary.csv',index=False)
    ymax=float(np.ceil(max(three.aBN1.max(),three.resource.max(),three.accumulator.max())/5)*5+1)
    macros={'PlotMax':f'{ymax:g}','RelativeVerdict':relative_text,'AbsoluteVerdict':absolute_text,'NextHypothesis':future,
            'ResourcePass':str(spass),'AccumulatorPass':str(ipass),
            'ResourceProspectiveRMSE':f"{c3['aggregate_scores']['resource']['rmse']:.3f}",
            'AccumulatorProspectiveRMSE':f"{c3['aggregate_scores']['accumulator']['rmse']:.3f}"}
    (data/'numbers.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+v+'}' for k,v in macros.items())+'\n')
    mdrows='\n'.join(f"| {labels[r['condition']]} | {names[r['surrogate']]} | {r['n']} | {r['mae']:.3f} | {r['rmse']:.3f} | {'通过' if r['mae_screen'] else '未通过'} |" for r in c3['scores'])
    runtime=sum(x['elapsed_seconds'] for x in c1['provenance'])+sum(x['elapsed_seconds'] for x in c3['provenance'])
    text=f'''# Habituation 阶段二：三轮闭环研究报告

## 结论先行

- **循环一：模型内记忆归因得到支持。** 初次aBN1均值8.2；训练后0.4；只清快状态仍0.4；恢复资源后8.2。5/5实现的双重状态恢复与初次全脑事件完全一致；5/5训练前后旁路事件完全一致。
- **循环二：旧下降曲线存在代理歧义。** 两种只拟合两个读出系数的代理，都能接近旧全脑输出；其生理含义不能据此被唯一识别。
- **循环三：{relative_text}。** {absolute_text}。
- **尚未确立：** 真实果蝇机制、完整行为习惯化、特异性/去习惯化，以及真实连接组相对于低维模型的独特优势。

## 三轮闭环

### 1. H1 → 状态干预 → 因果归因

在同一个M1训练末态派生sham、资源恢复、快状态恢复、两者恢复和旁路刺激。5个旧种子、90个响应窗口均保存全脑事件并独立回读。快状态包含v、g、lastspike和not_refractory；资源恢复为人工将x置1并同步更新时间戳。它不是新刺激B引发的生物去习惯化。

直接驱动aBN1时，未训练/训练后的aBN1、aDN1、aDN2均为10、2、3，完整事件也一致。说明本模型神经输出通路仍可被驱动，但不是肌肉或完整行为疲劳实验。恢复的是M1初次水平，不是M0原始基线。

**修正：** 不再把下降泛称为“全脑学会忽略刺激”；将解释收窄为本M1的资源状态介导历史效应。进而提出H2：粗粒度输出也许只需很小的动态代理。

### 2. H2 → 低维拟合与跨协议检查 → 机制歧义

资源代理S使用dx/dt=(1−x)/tau−Ufx；积累代理I使用dz/dt=(f/150−z)/tau。两者固定tau=2秒，S固定U=0.01，各拟合两个非负读出参数；完整方程见PDF和 `cycle2_spec.json`。

仅用旧M1短间隔60个训练窗口拟合。资源/积累代理拟合RMSE分别{c2['models']['resource']['fit_metrics']['rmse']:.3f}/{c2['models']['accumulator']['fit_metrics']['rmse']:.3f}；旧跨协议80个窗口的检查RMSE分别{c2['models']['resource']['retrospective_metrics']['rmse']:.3f}/{c2['models']['accumulator']['retrospective_metrics']['rmse']:.3f}。旧结果已看过，因此后者是回顾性检查，不是盲测。

**修正：** 单条下降曲线不能可靠区分这两种代理。它们是模拟器的低维代理，不是两个新的、已在连接组中实现的生物机制。

### 3. H3 → 主动设计 → 新数据检验

从18个事先规定的候选中，按照代理预测分歧选出200 Hz/400 ms/T=1.2秒，以及150 Hz/400 ms/T=1.2秒两组协议；另保留原形状的新种子对照。使用2701–2703三个新种子。**102个M1响应窗口的预测在任何新全脑结果之前冻结**；另有9个M0初态窗口用于正常传递对照。

主判据为每协议MAE≤1.5脉冲；未用新输出重新拟合。

| 协议 | 代理 | 窗口数 | MAE | RMSE | 绝对精度门槛 |
|---|---|---:|---:|---:|---|
{mdrows}

两个判别条件均同时检查相对MAE/RMSE排序。{relative_text}。{absolute_text}。每种协议只有3个输入实现，不进行生物总体显著性推断。

## 探索性细节：平均预测达标不等于逐步完全正确

在看过强刺激2701输出后，额外检查了非单调变化；这不是预设判据。200 Hz/400 ms条件的三个种子分别存在2/1/1脉冲的最大相邻上升，对应M1边资源均值仍下降。两种当前代理在相同固定输入下只预测下降或平台，因此不能精确再现这些局部反弹。其他两个协议未出现相邻上升。

这不影响它们按预先规定的MAE门槛评分，也不证明反弹必然由抑制回路导致。时序、空间网络和神经元重置非线性都可能参与；需要新的受控干预。见 `analysis/cycle3/exploratory_rebounds.csv`，保留全部九条序列而非只显示最大例子。

## 新的假设，而非继续调参求成功

{future} 新H4特别关注冻结输入下的局部反弹：在匹配平均率和初始状态时改变时序或细胞分配，是否会改变这类代理无法精确表示的细节？该下一轮实验尚未执行。

本阶段在三个循环完成后停止，不把测试集转成训练集，也不把相对胜出写成全部判据通过。新的机制假设需要下一轮新的冻结协议与新数据。

## 方法和科学边界

- 保持完整127,400神经元及14,687,178条原始聚合边；STD只在原先4,764条兴奋性输出边上工作。未修改旧基线、上游代码或第一版论文。
- 阶段二新增 **201个正式响应窗口**：循环一90个，循环三102+9个。独立回读{c1['raw_event_files_verified']+c3['audit']['raw_event_files_verified']}个事件文件。
- 新输入的命令事件到感觉脉冲映射也逐事件校验；不能只假定输入稳定。
- 循环一最初出现新增旁路发生器的状态恢复错误，失败输出保留并未纳入结论；修复后通过全事件门槛。详见 `LOOP_LOG.md`。
- 成功批次记录墙钟合计约{runtime:.1f}秒（{runtime/60:.1f}分钟），不是纯积分benchmark，未计失败启动、报告整理等开销。
- 全脑生理参数没有拟合；本阶段确实对两个低维代理各拟合了两个读出系数，不应与首轮“完全不拟合参数”的范围混同。
- 资源代理拥有与生成数据的M1一致的机制先验；结果检验压缩/外推，不是对未知生物机制的无先验裁决。固定时间常数和固定读出的积累代理失败，不等于否定所有积累模型或抑制性可塑性。
- 主动设计偏向两代理分歧大的区域，结果不代表整个刺激分布上的总体排名。
- 数据来自一个计算图谱，不是多个活体动物。旁路响应可用不等于已排除所有生物疲劳解释。

## 证据导航

- [阶段冻结方案](PROTOCOL.md)、[研究循环日志](LOOP_LOG.md)
- [循环一审计](analysis/cycle1/report.json)、[逐种子因果得分](analysis/cycle1/scores.csv)
- [冻结代理与参数](analysis/cycle2/frozen_models.json)、[运行前逐窗口预测](analysis/cycle2/prospective_predictions.csv)
- [循环三审计及评分](analysis/cycle3/report.json)、[预测与观测配对](analysis/cycle3/forecast_outcomes.csv)
- [阶段报告PDF](report.pdf)、[LaTeX源文件](report.tex)

主要理论和生物文献：Rankin et al. (2009), DOI 10.1016/j.nlm.2008.09.012；Smart et al. (2024), DOI 10.1073/pnas.2409330121；Shiu et al. (2024), DOI 10.1038/s41586-024-07763-9；Das et al. (2011), DOI 10.1073/pnas.1106411108。已知嗅觉/味觉抑制机制不自动成为JO-CE机制证据。
'''
    (HERE/'REPORT.md').write_text(text)
    summary={'resource_better_in_both_discriminating_designs':relative,'resource_mae_pass_conditions':spass,'accumulator_mae_pass_conditions':ipass,
             'formal_new_windows':201,'raw_event_files_verified':c1['raw_event_files_verified']+c3['audit']['raw_event_files_verified'],'successful_batch_wall_seconds':runtime,
             'source_sha256':{str(p.relative_to(HERE)):base.sha(p) for p in [HERE/'analysis/cycle1/report.json',HERE/'analysis/cycle2/frozen_models.json',HERE/'analysis/cycle3/report.json',Path(__file__)]}}
    base.write_json(HERE/'stage_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
