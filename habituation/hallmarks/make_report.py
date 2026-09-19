#!/usr/bin/env python3
"""Data-driven report material; does not run a simulation or change thresholds."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_experiment as base
pd,np=base.pd,base.np
HERE=Path(__file__).resolve().parent


def bracket(x):
    if x['status']=='undefined':return '未定义'
    lo=x['lower_ms']/1000;hi=x['upper_ms']
    text=f'>{lo:g}s' if hi is None else ('[' if lo==0 else '(')+f'{lo:g}, {hi/1000:g}]s'
    return text if x['monotone'] else text+'（非单调，不能作速度界限）'


def main():
    root=HERE/'analysis/final';r=json.loads((root/'report.json').read_text())
    base.require({p['part'] for p in r['provenance']}=={'main','novel','partial','frequency'},'Incomplete report inputs')
    base.require(r['actual_input_sequences_verified'],'Input confounding requires manual review before report')
    g=r['groups'];scores=r['screens'];data=HERE/'report_data';data.mkdir(exist_ok=True)
    tm=pd.read_csv(root/'training_metrics.csv');ptm=pd.read_csv(root/'partial_training_metrics.csv')
    main_df=pd.read_csv(root/'main_responses.csv');partial=pd.read_csv(root/'partial_responses.csv');profiles=pd.read_csv(root/'recovery_profiles.csv')
    qualified=[s for s in scores if s['hallmark']=='H4b_qualified']
    absolute_fast=sum(s['eligible'] and s['absolute_80_high_faster'] for s in qualified)
    absolute_slow=sum(s['eligible'] and s['absolute_80_low_faster'] for s in qualified)
    status={
        'H1':'此前支持；本轮继续观察重复刺激递减',
        'H2':'此前支持；本轮增加五点独立恢复探测',
        'H3':f"2秒部分恢复条件 {g['H3_partial']['supported']}/3 支持补充筛查；10秒条件 {g['H3']['supported']}/3 达到原较严格门槛",
        'H4(a)':'比较同为12次训练的0.5/1秒起始间隔；见实际D，不与输入强度混同',
        'H4(b)':f"原比较仅{g['H4b']['eligible']}/3具资格；24次补测{g['H4b_qualified']['eligible']}/3具资格，F50支持{g['H4b_qualified']['supported']}/3；首次80%高频明确更早{absolute_fast}/3，仍未稳健建立", 
        'H5':f"弱输入更强递减：{g['H5']['supported']}/3 达到预设效应量；限于人工神经输入率",
        'H6':f"12→24次额外训练：{g['H6']['supported']}/3 出现预设的恢复变化",
        'H7':'两个候选B均未达到可比较的aBN1基线；无法判定，不是阴性',
        'H8':'两个B均有效激活网络，但都未恢复A超过等时休息；本协议未观察到',
        'H9':'H8没有可靠解除效应，前提不满足，未继续测试',
        'H10':'未测试：无长期机制或相应长期生物测定标定'}
    weak=tm[tm.case=='fast12'];strong=tm[tm.case=='strong12'];slow=tm[tm.case=='slow12']
    h1=int((weak.initial_usable&weak.decrement).sum())
    h2=int((profiles[(profiles.case=='fast12')&(profiles.rest_ms==5000)].relative_initial>=.8).sum())
    h4a=int((weak.set_index('seed').D>slow.set_index('seed').D).sum())
    h5direction=sum(s['weak_minus_strong_D']>0 for s in scores if s['hallmark']=='H5')
    status['H1']=f"基准短间隔{h1}/3继续出现递减，平均D={weak.D.mean()*100:.1f}%"
    status['H2']=f'基准短间隔训练后，5秒探测{h2}/3恢复至首次至少80%'
    status['H4(a)']=f"{h4a}/3高重复频率递减更强；T=0.5/1秒的平均D为{weak.D.mean()*100:.1f}%/{slow.D.mean()*100:.1f}%"
    status['H5']=f"弱/强输入平均D={weak.D.mean()*100:.1f}%/{strong.D.mean()*100:.1f}%；方向{h5direction}/3一致，{g['H5']['supported']}/3达到预设≥10个百分点差异"
    windows=sum(p['response_windows'] for p in r['provenance']);files=sum(p['raw_event_files'] for p in r['provenance']);runtime=sum(p['elapsed_seconds'] for p in r['provenance'])
    overview='\n'.join(f'| {k} | {v} |' for k,v in status.items())
    h3lines=[]
    for s in scores:
        if s['hallmark']=='H3_partial':
            h3lines.append(f"| {s['seed']} | {' / '.join(f'{v:g}' for v in s['initial_by_cycle'])} | {' / '.join(f'{v:.2f}' for v in s['early_by_cycle'])} | {s['half_trial_common_baseline']} | {s['half_trial_own_baseline']} |")
    h4lines=[];h4tex=[]
    for s in scores:
        if s['hallmark']=='H4b':
            vals=[str(s['seed']),bracket(s['fast_half_interval']),bracket(s['slow_half_interval']),bracket(s['fast_80_interval']),bracket(s['slow_80_interval'])]
            h4lines.append('| '+' | '.join(vals)+' |');h4tex.append(' & '.join(vals)+r' \\')
    (data/'recovery_intervals.tex').write_text('\n'.join(h4tex)+'\n')
    fq=pd.read_csv(root/'frequency_recovery_profiles.csv');ftm=pd.read_csv(root/'frequency_training_metrics.csv')
    qualified_lines=[];qualified_tex=[]
    for s in qualified:
        vals=[str(s['seed']),bracket(s['fast_half_interval']),bracket(s['slow_half_interval']),bracket(s['fast_80_interval']),bracket(s['slow_80_interval'])]
        qualified_lines.append('| '+' | '.join(vals)+' |');qualified_tex.append(' & '.join(vals)+r' \\')
    (data/'qualified_intervals.tex').write_text('\n'.join(qualified_tex)+'\n')
    for case in ['fast24','frequency24']:
        p=fq[fq.case==case].groupby('rest_ms')[['aBN1','F','relative_initial']].mean().reset_index();p['rest_s']=p.rest_ms/1000;p.to_csv(data/f'qualified_{case}.csv',index=False)
    strength=[];strengthtex=[]
    for seed in sorted(tm.seed.unique()):
        h=tm[tm.seed==seed].set_index('case');a=h.loc['fast12'];b=h.loc['strong12'];c=h.loc['slow12']
        strength.append(f"| {seed} | {a.initial:g} | {b.initial:g} | {a.D*100:.1f}% | {b.D*100:.1f}% | {c.D*100:.1f}% |")
        strengthtex.append(f'{seed} & {a.initial:g} & {b.initial:g} & {a.D*100:.1f} & {b.D*100:.1f} & {c.D*100:.1f}'+r' \\')
    (data/'strength.tex').write_text('\n'.join(strengthtex)+'\n')
    h6lines=[]
    for s in scores:
        if s['hallmark']=='H6':h6lines.append(f"| {s['seed']} | {'是' if s['eligible'] else '否'} | {s['probe_differences_24_minus_12']} | {'是' if s['supported'] else '否'} |")
    b_lines=[];b_tex=[]
    for s in scores:
        if s['hallmark']=='H8':
            name='JO-F' if s['B']=='neu_JON_F' else 'JO-D候选'
            b_lines.append(f"| {s['seed']} | {name} | {s['B_naive_noninput_spikes']} | {s['A_sham']} | {s['A_after_B']} | {s['trained_gain']} | {s['naive_gain']} |")
            b_tex.append(f"{s['seed']} & {name} & {s['B_naive_noninput_spikes']} & {s['A_sham']} & {s['A_after_B']} & {s['trained_gain']}"+r' \\')
    (data/'B_controls.tex').write_text('\n'.join(b_tex)+'\n')
    cycles=[]
    for delay,df in [(10,main_df),(2,partial)]:
        for block in [1,2,3]:
            if delay==10:
                sel=df[(df.case=='fast12')&(df.phase=='train')] if block==1 else df[(df.case=='h3')&(df.phase=='train')&(df.block==block)]
            else:sel=df[(df.phase=='train')&(df.block==block)]
            c=sel.groupby('pulse').aBN1.agg(['mean','min','max']).reset_index();c['trial']=c.pulse+1;c.to_csv(data/f'cycles_{delay}s_{block}.csv',index=False)
            cycles.append({'rest_s':delay,'block':block,'initial':float(sel[sel.pulse==0].aBN1.mean()),'early':float(sel[sel.pulse<3].aBN1.mean()),'late':float(sel[sel.pulse>=9].aBN1.mean())})
    pd.DataFrame(cycles).to_csv(data/'cycles_summary.csv',index=False)
    for case in ['fast12','slow12','fast24']:
        p=profiles[profiles.case==case].groupby('rest_ms')[['aBN1','F','relative_initial']].mean().reset_index();p['rest_s']=p.rest_ms/1000;p.to_csv(data/f'recovery_{case}.csv',index=False)
    for case in ['fast12','strong12']:
        p=main_df[(main_df.case==case)&(main_df.phase=='train')].groupby('pulse').aBN1.mean().reset_index();p['trial']=p.pulse+1;p.to_csv(data/f'strength_{case}.csv',index=False)
    macros={'PartialPass':str(g['H3_partial']['supported']),'FullPass':str(g['H3']['supported']),'FrequencyPass':str(g['H4b']['supported']),
            'StrengthPass':str(g['H5']['supported']),'AccumulationPass':str(g['H6']['supported']),'Windows':str(windows),'EventFiles':str(files),'WallMinutes':f'{runtime/60:.2f}',
            'QualifiedEligible':str(g['H4b_qualified']['eligible']),'QualifiedPass':str(g['H4b_qualified']['supported']),'AbsoluteFast':str(absolute_fast),'AbsoluteSlow':str(absolute_slow)}
    (data/'numbers.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+v+'}' for k,v in macros.items())+'\n')
    text=f'''# Habituation hallmarks 补测结果

## 总览

本轮在原完整M1中进行新实验，没有改变U/tau、拟合参数或人工恢复资源。三个新输入实现3701–3703；共 **{windows}个300ms观测窗口**（包含6个无A输入的残留输出检查窗），独立回读 **{files}个完整事件文件**（含静默间隔）。成功计算批次记录合计{runtime/60:.2f}分钟，不是纯积分benchmark。

| 特征 | 本轮证据状态 |
|---|---|
{overview}

**这些筛查只是模型神经读出的操作性标准，不是证明真实果蝇具备相同机制。未通过阈值不等于数学上绝不可能出现该特征；缺少适用条件也不等于阴性。**

## H3：必须区分部分恢复与近充分恢复

原主协议为轮间10秒、三轮各12次；保留首次恢复≥80%及原D/半响应速度门槛。结果{g['H3']['supported']}/3达到该较严格门槛。

文献复核发现，Smart et al. (2024)的H3数学表述允许部分恢复。因此，在主实验多轮/恢复结果读取前另冻结2秒休息补充；当时已见第二刺激实验的单轮A基线。该补充不替换主协议，不搜索其他时长。2秒条件{g['H3_partial']['supported']}/3达到补充筛查。

| 种子 | 各轮首次 | 各轮前3次均值 | 共同首轮基准的半响应序号 | 各轮自身基准的半响应序号 |
|---|---|---|---|---|
{chr(10).join(h3lines)}

部分恢复下响应进一步下降可以由残余资源状态解释。共同基准下更早降到阈值，与相对每轮起点的下降速度变化不是一回事。即使支持H3样现象，也不能称为新的长期记忆、学习率改变或元可塑性；本模型的tau/U从未改变。

## H4(b)：恢复速度仍需看定义和分辨率

两组均12次、同强度150Hz，只改变刺激起始间隔0.5/1秒。各自从相同末态独立等待0.2、0.5、1、2、5秒，再用相同A探测。

主筛查以F=(探测−末3次)/(首次−末3次)衡量“已损失响应恢复了多少”；另报告“探测/首次”达到80%的时间。下表是首次观测过阈附近的采样区间，不是拟合时间常数或置信区间。非单调曲线不能拿首次越阈证明速度排序。

| 种子 | 高频F50区间 | 低频F50区间 | 高频首次80%区间 | 低频首次80%区间 |
|---|---|---|---|---|
{chr(10).join(h4lines)}

一个重要时间定义限制：对T=1秒组，0.2/0.5秒等待加上300ms读出窗后，探测起始间隔只有0.5/0.8秒，反而短于通常的1秒训练间隔。这两个点是短间隔探测，不能单独当作“漏掉刺激后的恢复”；负F也不表示产生了新的长期抑制。靠近初次水平的比较须看较晚探测。

F50操作性主筛查{g['H4b']['supported']}/3支持。即使某些F值更高，也不能忽略不同的末态损失深度，更不能在采样区间相同时强行给出恢复时间差。完整H4(b)的判断必须结合首次响应恢复与曲线排序，见逐种子 `screens.csv` 和全部恢复点 `recovery_profiles.csv`。

### 一次限定的资格补测（保留原结果）

原比较只有{g['H4b']['eligible']}/3满足全部先决条件：3701的慢组平台差0.667大于门槛0.600，3703慢组D=29.4%低于30%。未将这些情况写成H4(b)阴性，也未放宽阈值。另行冻结T=0.75秒、24次的新条件，与已有T=0.5秒、24次匹配；探测0.5/1/2/5秒，不再含提前于正常训练间隔的点。新增这一组后即停止扩大。

新比较{g['H4b_qualified']['eligible']}/3满足原递减/平台门槛。F50操作性支持{g['H4b_qualified']['supported']}/3；以达到首次80%计，高频明确较早{absolute_fast}/3，低频明确较早{absolute_slow}/3，其余未分辨。

| 种子 | 高频F50区间 | 较低频F50区间 | 高频首次80%区间 | 较低频首次80%区间 |
|---|---|---|---|---|
{chr(10).join(qualified_lines)}

采样单调假定下，区间左端为尚未过阈的探测时刻、右端为第一次观测过阈；`>5s`表示5秒时仍未达阈，不能给出具体恢复常数。不能把多数相同采样区间称为统计等价，也不据单一实现或单一分母宣布完整H4(b)。新设计是在看过主实验资格结果后固定，不是原主协议的一部分，详见[补充方案](FREQUENCY_SUPPLEMENT.md)。

## H5：强度依赖的新数据检验

150/200Hz是每次200ms刺激期间的感觉神经输入率；重复刺激间隔均为0.5秒。它不同于H4所说的刺激重复频率。三个实现中{g['H5']['supported']}/3达到弱输入D高出至少0.10的预设门槛。这里D先逐实现计算，再描述，不用不同初始幅度的原始计数直接冒充比例递减。

| 种子 | 150Hz首次 | 200Hz首次 | 150Hz D | 200Hz D | 150Hz、T=1秒 D（H4对照） |
|---|---:|---:|---:|---:|---:|
{chr(10).join(strength)}

## H6：已经到平台后，再训练12次有什么变化？

比较同一历史的第12次和第24次末态，各自做五个独立恢复探测。只有两者均满足平台门槛才进行该筛查。差值为24次−12次训练后的aBN1计数，顺序对应休息0.2/0.5/1/2/5秒。

| 种子 | 平台等条件满足 | 五点恢复计数差 | 达到预设变化门槛 |
|---|---|---|---|
{chr(10).join(h6lines)}

本比较{g['H6']['supported']}/3支持预设可测影响。资源变量仍有极小变化本身不算读出层面H6；本结果也不排除更早停止训练、不同刺激或不同机制下的潜隐积累。

## H7/H8/H9：第二刺激确实测试了什么

两种B是上游明确列出的不同JON群体，未随意挑选神经元或强行抬高强度。B输入接口在其全部对照中保持相同，STD仍只位于JO-CE输出。两个B的未训练aBN1都是0，因此H7缺少可比较的初态读出，不能把“B一直为零”判成特异性。

H8不要求B自身激活aBN1。这里两个B都超过预设的100个非输入神经元脉冲，且B→空白窗aBN1为0；因而可比较训练后B→A与等时休息→A，并用未训练B→A检查一般增益。

| 种子 | B | 未训练B的非输入脉冲 | 等时休息后A | 插入B后A | 训练背景增益 | 未训练背景增益 |
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(b_lines)}

两个候选的增益均为0，故**这些B、强度与时序未诱发去习惯化**。不能推广为所有B都无效，也不能把人工恢复资源与本次真实神经刺激混同。因为没有可靠解除效应，H9没有继续测试的先决条件。

## H10与证据边界

没有长期可塑性、对应生物读出及长期协议标定，故不把本轮秒级保持/恢复叫作长期习惯化；也没有把tau人为拉长后宣称通过H10。

所有结果来自同一连接组的三种随机输入实现，不是三只动物。主实验、B接口实验、部分恢复补充的首次训练事件等价检查分别为：B接口={r['main_vs_B_interface_train_event_hashes_equal']}，2秒补充={r['main_vs_partial_first_cycle_event_hashes_equal']}。实际感觉事件全部通过逐事件校验；所有静默间隔也保存了原始事件。原始上游、旧实验和既有PDF未覆盖，未提交或推送。

完整资格补测的首次全脑事件与原主实验也相同：{r['frequency_initial_event_hashes_equal']}。H3连续2秒恢复后的首个探测，与主实验独立恢复分支的全事件对照：{r['continuous_partial_matches_independent_2s_probe']}。

## 文件导航

- [预先规定主方案](PROTOCOL.md)、[恢复解释补充](RECOVERY_INTERPRETATION.md)、[部分恢复H3补充](H3_PARTIAL_RECOVERY.md)、[日志](LAB_NOTES.md)
- [最终完整审计](analysis/final/report.json)、[逐实现筛查](analysis/final/screens.csv)、[训练指标](analysis/final/training_metrics.csv)、[主恢复曲线](analysis/final/recovery_profiles.csv)、[资格补测恢复曲线](analysis/final/frequency_recovery_profiles.csv)
- [补测前的完整主分析](analysis/full/report.json)保留不变，不覆盖原结果
- [复现说明](README.md)

参考：Rankin et al. (2009), DOI 10.1016/j.nlm.2008.09.012；Smart et al. (2024), DOI 10.1073/pnas.2409330121。后者的形式化指标不能不加说明地视为所有生物实验的唯一标准。
'''
    (HERE/'REPORT.md').write_text(text)
    summary={'windows':windows,'raw_event_files':files,'wall_seconds':runtime,'hallmark_status':status,
             'source_sha256':{str(p.relative_to(HERE)):base.sha(p) for p in [root/'report.json',root/'main_responses.csv',root/'partial_responses.csv',root/'training_metrics.csv',root/'recovery_profiles.csv',root/'frequency_recovery_profiles.csv',root/'frequency_training_metrics.csv',Path(__file__)]}}
    base.write_json(HERE/'report_summary.json',summary)
    print(json.dumps({'windows':windows,'files':files,'wall_minutes':runtime/60,'status':status},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
