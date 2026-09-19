#!/usr/bin/env python3
"""Read audited summaries, reconcile counts and regenerate integrated tables/plots.
Standard library only. No simulation, optimisation, or rewriting old artifacts.
"""
import csv
import hashlib
import json
import math
import statistics as st
from pathlib import Path

HERE=Path(__file__).resolve().parent
HAB=HERE.parent
DATA=HERE/'data'
USED=set()


def read_bytes(name):
    p=HAB/name;USED.add(p);return p.read_bytes()


def rows(name):
    return list(csv.DictReader(read_bytes(name).decode().splitlines()))


def obj(name):return json.loads(read_bytes(name))


def mean(values):return st.mean(float(v) for v in values)


def table(name,values):
    (DATA/name).write_text('\n'.join(' & '.join(map(str,row))+r' \\' for row in values)+'\n')


def write_csv(name,fields,values):
    with (DATA/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(values)


def curve(name,records,key='pulse'):
    out=[]
    for k in sorted({int(r[key]) for r in records}):
        group=[float(r['aBN1']) for r in records if int(r[key])==k]
        out.append({'trial':k+1,'mean':st.mean(group),'min':min(group),'max':max(group)})
    write_csv(name,['trial','mean','min','max'],out)


def bracket(value):
    lo=value['lower_ms'];hi=value['upper_ms']
    if lo is None:return '未定义'
    if hi is None:return f'$>{lo/1000:g}$'
    return f'$({lo/1000:g},{hi/1000:g}]$' if lo else f'$[0,{hi/1000:g}]$'


def main():
    DATA.mkdir(exist_ok=True)
    first=obj('analysis/report.json');causal=obj('stage2/analysis/cycle1/report.json')
    forecast=obj('stage2/analysis/cycle3/report.json');hall=obj('hallmarks/analysis/final/report.json')
    frozen=obj('stage2/analysis/cycle2/frozen_models.json')
    base=rows('analysis/responses.csv');metrics=rows('analysis/metrics_by_seed.csv')
    cr=rows('stage2/analysis/cycle1/responses.csv');outcomes=rows('stage2/analysis/cycle3/forecast_outcomes.csv')
    new=rows('stage2/analysis/cycle3/responses.csv')
    hm=rows('hallmarks/analysis/final/main_responses.csv');hp=rows('hallmarks/analysis/final/partial_responses.csv')
    hn=rows('hallmarks/analysis/final/novel_responses.csv');hq=rows('hallmarks/analysis/final/frequency_responses.csv')
    assert len(base)==280 and len(cr)==90 and len(outcomes)==102 and len(new)==111
    assert sum(map(len,[hm,hp,hn,hq]))==525
    total=len(base)+len(cr)+len(new)+sum(map(len,[hm,hp,hn,hq]));assert total==1006
    raw=first['audit']['raw_event_files_checked']+causal['raw_event_files_verified']+forecast['audit']['raw_event_files_verified']+sum(p['raw_event_files'] for p in hall['provenance']);assert raw==1212
    seeds={int(r['seed']) for collection in [base,cr,new,hm,hp,hn,hq] for r in collection};assert len(seeds)==11
    assert hashlib.sha256(read_bytes('stage2/analysis/cycle2/prospective_predictions.csv')).hexdigest()==forecast['frozen_predictions_sha256']==frozen['prediction_sha256']
    assert hashlib.sha256(read_bytes('stage2/analysis/cycle2/frozen_models.json')).hexdigest()==forecast['frozen_models_sha256']
    assert first['audit']['sensory_event_trains_identical_within_seed'] and hall['actual_input_sequences_verified']
    assert forecast['audit']['forecast_precedes_all_simulation_runs']
    baseline=[]
    for model in ['static','std']:
        for T in [500,2000]:
            g=[r for r in metrics if r['model']==model and float(r['interval_ms'])==T]
            baseline.append([('M0' if model=='static' else 'M1')+f' / {T/1000:g}s',*[f'{mean(r[k] for r in g):.2f}' for k in ['initial','early_mean','late_mean']],f'{100*mean(r["decrement_fraction"] for r in g):.2f}',*[f'{mean(r[k] for r in g):.2f}' for k in ['probe_2000','probe_10000']]])
            records=[r for r in base if r['model']==model and float(r['interval_ms'])==T and r['phase']=='train']
            curve(f'base_{model}_{T}.csv',records)
    table('baseline.tex',baseline)
    table('individual.tex',[[r['seed'],f'{float(r["interval_ms"])/1000:g}',*[f'{float(r[k]):.2f}' for k in ['initial','early_mean','late_mean']],f'{float(r["decrement_fraction"])*100:.2f}',r['probe_2000'],r['probe_10000']] for r in metrics if r['model']=='std'])
    labels=[('train','初次'),('sham','训练后'),('fast_reset','清快状态'),('resource_reset','恢复资源'),('both_reset','双重恢复')]
    values=[];ct=[]
    for i,(phase,label) in enumerate(labels):
        g=[r for r in cr if r['phase']==phase and (phase!='train' or int(r['pulse'])==0)]
        y=[float(r['aBN1']) for r in g];assert len(y)==5
        values.append({'x':i,'mean':st.mean(y),'minus':st.mean(y)-min(y),'plus':max(y)-st.mean(y)})
        ct.append([label,f'{st.mean(y):.2f}',f'{min(y):g}--{max(y):g}'])
    table('causal.tex',ct);write_csv('causal.csv',['x','mean','minus','plus'],values)
    fit=[]
    for key,label in [('resource','资源S'),('accumulator','积累I')]:
        m=frozen['models'][key];fit.append([label,f'{m["A"]:.6f}',f'{m["B"]:.6f}',f'{m["fit_metrics"]["rmse"]:.3f}',f'{m["retrospective_metrics"]["rmse"]:.3f}'])
        errors=[float(r[key])-float(r['aBN1']) for r in outcomes]
        assert math.isclose(math.sqrt(mean(e*e for e in errors)),forecast['aggregate_scores'][key]['rmse'],abs_tol=1e-12)
    table('fit.tex',fit)
    names={'new_seed_control':'新种子对照','f200_p400_gap800':'200Hz长刺激','f150_p400_gap800':'150Hz长刺激'}
    scores=rows('stage2/analysis/cycle3/scores_by_condition.csv')
    scores.sort(key=lambda r:(list(names).index(r['condition']),{'resource':0,'accumulator':1}[r['surrogate']]))
    table('forecasts.tex',[[names[r['condition']], 'S' if r['surrogate']=='resource' else 'I',r['n'],f'{float(r["mae"]):.3f}',f'{float(r["rmse"]):.3f}','是' if r['mae_screen']=='True' else '否'] for r in scores])
    for i,condition in enumerate(names):
        g=[r for r in outcomes if r['condition']==condition and r['phase']=='train'];out=[]
        for k in sorted({int(r['pulse']) for r in g}):
            v=[r for r in g if int(r['pulse'])==k]
            out.append({'trial':k+1,**{key:mean(r[key] for r in v) for key in ['aBN1','resource','accumulator']}})
        write_csv(f'forecast_{i}.csv',['trial','aBN1','resource','accumulator'],out)
    rb=rows('stage2/analysis/cycle3/exploratory_rebounds.csv')
    table('rebounds.tex',[[r['seed'],f'{int(r["from_stimulus"])}$\\to${int(r["to_stimulus"])}',f'{float(r["response_before"]):g}$\\to${float(r["response_after"]):g}',f'{float(r["resource_state_change"]):.6f}',f'{float(r["resource_prediction_change"]):.3f}'] for r in rb if r['condition']=='f200_p400_gap800'])
    for delay in [2,10]:
        for block in [1,2,3]:
            if delay==2:g=[r for r in hp if r['phase']=='train' and int(r['block'])==block]
            else:g=[r for r in hm if r['phase']=='train' and ((block==1 and r['case']=='fast12') or (block>1 and r['case']=='h3' and int(r['block'])==block))]
            curve(f'h3_{delay}_{block}.csv',g)
    screens=hall['screens']
    table('h3.tex',[[s['seed'],' / '.join(f'{x:g}' for x in s['initial_by_cycle']),' / '.join(f'{x:.2f}' for x in s['early_by_cycle']),' / '.join(map(str,s['half_trial_common_baseline'])),' / '.join(map(str,s['half_trial_own_baseline']))] for s in screens if s['hallmark']=='H3_partial'])
    table('h5.tex',[[s['seed'],f'{100*s["D_150"]:.1f}',f'{100*s["D_200"]:.1f}',f'{100*s["weak_minus_strong_D"]:.1f}','是' if s['supported'] else '否'] for s in screens if s['hallmark']=='H5'])
    for s in screens:
        if s['hallmark']=='H6':assert s['probe_differences_24_minus_12']==[0]*5
    table('h4.tex',[[s['seed'],bracket(s['fast_half_interval']),bracket(s['slow_half_interval']),bracket(s['fast_80_interval']),bracket(s['slow_80_interval'])] for s in screens if s['hallmark']=='H4b_qualified'])
    table('b_controls.tex',[[s['seed'],'JO-F' if s['B']=='neu_JON_F' else 'JO-D候选',s['B_naive_noninput_spikes'],s['A_sham'],s['A_after_B'],s['trained_gain'],s['naive_gain']] for s in screens if s['hallmark']=='H8'])
    for filename,prefix in [('hallmarks/analysis/final/recovery_profiles.csv','original'),('hallmarks/analysis/final/frequency_recovery_profiles.csv','qualified')]:
        rr=rows(filename)
        for case in sorted({r['case'] for r in rr}):
            out=[]
            for t in sorted({float(r['rest_ms']) for r in rr if r['case']==case}):
                g=[r for r in rr if r['case']==case and float(r['rest_ms'])==t]
                out.append({'rest_s':t/1000,**{k:mean(r[k] for r in g) for k in ['aBN1','F','relative_initial']}})
            write_csv(f'{prefix}_{case}.csv',['rest_s','aBN1','F','relative_initial'],out)
    groups=hall['groups'];assert groups['H3_partial']['supported']==3 and groups['H3']['supported']==0
    assert groups['H5']['supported']==2 and groups['H4b_qualified']['eligible']==3 and groups['H4b_qualified']['supported']==0
    source_paths=['paper/report.pdf','stage2/report.pdf','hallmarks/report.pdf','RESULTS.md','stage2/REPORT.md','hallmarks/REPORT.md','hallmarks/PROTOCOL.md','hallmarks/H3_PARTIAL_RECOVERY.md','hallmarks/FREQUENCY_SUPPLEMENT.md','stage2/PROTOCOL.md']
    for p in source_paths:read_bytes(p)
    summary={'formal_observation_windows':total,'raw_event_files_previously_audited':raw,'distinct_seed_identifiers':sorted(seeds),
             'blank_windows':6,'independent_animals':0,'new_simulations':0,'new_fits':0,
             'resource_prospective_rmse':forecast['aggregate_scores']['resource']['rmse'],'accumulator_prospective_rmse':forecast['aggregate_scores']['accumulator']['rmse'],
             'hallmark_groups':groups,'scope':'Retrospective synthesis of existing audited studies; counts are not independent samples.'}
    (HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    manifest={'sources_sha256':{str(p.relative_to(HAB)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(USED)},
              'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'generated_sha256':{str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DATA.iterdir())}}
    (HERE/'data_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
