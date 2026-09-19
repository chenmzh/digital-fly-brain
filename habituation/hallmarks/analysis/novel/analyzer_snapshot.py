#!/usr/bin/env python3
"""Independent raw-event, chronology, input and hallmark audit."""
import argparse
import json
from pathlib import Path
import sys
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import run_experiment as base
from metrics import train_metrics,recovery_metrics,h3_screen,strictly_earlier,expected_schedule
pd,np=base.pd,base.np


def expected_input(pattern,ids):
    last=np.full(len(ids),-10000,dtype=int);events=[]
    for neuron,tick in zip(*pattern):
        if tick>last[neuron]+1:
            events.append((int(tick+1),int(ids[neuron])));last[neuron]=tick
    return pd.DataFrame(events,columns=['tick','flywire_id'],dtype=np.int64).sort_values(['tick','flywire_id']).reset_index(drop=True)


def audit(root,spec):
    m=json.loads((root/'manifest.json').read_text());base.require(m['status']=='completed','Incomplete hallmark run')
    base.require(m['completed_seeds']==spec['seeds'],'Incomplete seed coverage')
    base.require(json.loads((root/'protocol.json').read_text())==spec,'Protocol changed')
    for name,digest in m['source_sha256'].items():
        source=root/'runner_snapshot.py' if name.endswith('/hallmarks/run.py') else base.ROOT/name
        base.require(base.sha(source)==digest,'Source drift: '+name)
    for filename,key in [('intervals.csv','intervals_sha256'),('responses.csv','responses_sha256')]:
        base.require(base.sha(root/filename)==m[key],'Changed CSV')
    d=pd.read_csv(root/'intervals.csv');r=pd.read_csv(root/'responses.csv')
    pd.testing.assert_frame_equal(d[d.kind=='response'].reset_index(drop=True),r)
    cells=json.loads((root/'neuron_ids.json').read_text());pop={k:np.array(v,dtype=np.int64) for k,v in cells['inputs'].items()}
    for k,ids in pop.items():base.require(list(ids)==base.inputs_from_notebook('neu_JON_CE' if k=='A' else k),'Population drift')
    union=set(np.concatenate(list(pop.values())))
    known=set(pd.read_csv(base.COMP,index_col=0).index.astype(np.int64));registry={x['file']:x for x in m['files']}
    base.require(len(registry)==len(m['files']),'Duplicate registry entries')
    schedule=pd.DataFrame(expected_schedule(m['part'],spec));checks=[];quiet_events=0;actual_signatures={}
    for seed in spec['seeds']:
        g=d[d.seed==seed].reset_index(drop=True)
        base.require(len(g)==len(schedule),'Missing/extra interval')
        for key in schedule.columns:
            if key=='onset_s':base.require(np.allclose(g[key],schedule[key],rtol=0,atol=1e-8),'Off-schedule clock')
            else:base.require(list(g[key])==list(schedule[key]),'Off-schedule '+key)
        patterns={};expected={}
        for label,ids in pop.items():
            for hz in ([150.,200.] if label=='A' else [150.]):
                name=f'pattern_s{seed}_{label}_{int(hz)}.npz';path=root/name
                base.require(base.sha(path)==registry[name]['sha256'],'Pattern file changed')
                saved=np.load(path);p={'pulse_ms':spec['pulse_ms'],'dt_ms':spec['dt_ms'],'input_hz':hz}
                pattern=base.input_pattern(seed,len(ids),p)
                np.testing.assert_array_equal(saved['input_index'],pattern[0]);np.testing.assert_array_equal(saved['tick'],pattern[1])
                patterns[(label,hz)]=pattern;expected[(label,hz)]=expected_input(pattern,ids)
        for row in g.itertuples():
            path=root/row.event_file;base.require(base.sha(path)==registry[path.name]['sha256'],'Changed raw events')
            e=pd.read_parquet(path)
            base.require(e.tick.dtype==np.int64 and e.flywire_id.dtype==np.int64,'Integer precision')
            base.require(not e.duplicated().any(),'Duplicate events')
            base.require(set(e.flywire_id).issubset(known),'Unknown neuron')
            base.require(((e.tick>=0)&(e.tick<round(row.duration_ms/spec['dt_ms']))).all(),'Event outside interval')
            base.require(len(e)==row.total_spikes==registry[path.name]['events'],'Total mismatch')
            for k,ident in cells['readouts'].items():base.require((e.flywire_id==int(ident)).sum()==getattr(row,k),'Readout mismatch')
            base.require((~e.flywire_id.isin(union)).sum()==row.noninput_spikes,'Noninput mismatch')
            base.require(e.flywire_id.isin(pop['A']).sum()==row.sensory_A,'A input mismatch')
            base.require(0<=row.resource_before<=1+1e-12 and 0<=row.resource_after<=1+1e-12,'Resource bounds')
            if row.label!='blank':
                key=(row.label,row.input_hz);actual=e[e.flywire_id.isin(pop[row.label])].reset_index(drop=True)
                base.require(len(actual)==row.stimulus_spikes and len(patterns[key][0])==row.input_events,'Stimulus count mismatch')
                matches=actual.equals(expected[key])
                checks.append({'seed':seed,'event_file':row.event_file,'label':row.label,'matches_expected':matches})
            else:
                base.require(row.input_events==0 and row.stimulus_spikes==0,'Unexpected blank input')
            if row.kind=='quiet':quiet_events+=len(e)
            if row.kind=='response' and row.phase=='train' and row.case in ['fast12','novel_train']:
                actual_signatures[(seed,row.pulse)]=base.sha(path)
    base.require(len(r)==(261 if m['part']=='main' else 72),'Response coverage')
    base.require(set(d.event_file).issubset(registry),'Unregistered events')
    return r,{'part':m['part'],'path':str(root.relative_to(base.ROOT)),'manifest_sha256':base.sha(root/'manifest.json'),
              'raw_event_files':len(d),'response_windows':len(r),'quiet_spikes':quiet_events,
              'input_event_checks':len(checks),'input_event_mismatches':sum(not x['matches_expected'] for x in checks),
              'elapsed_seconds':m['elapsed_seconds'],'peak_rss_mib':m['peak_rss_mib']},pd.DataFrame(checks),actual_signatures


def main_scores(d,spec):
    scores=[];profiles=[];trains=[]
    for seed in spec['seeds']:
        g=d[d.seed==seed]
        values={}
        for case in ['fast12','slow12','strong12']:
            v=g[(g.case==case)&(g.phase=='train')].sort_values('pulse').aBN1.to_list();values[case]=v
        extra=g[(g.case=='fast24')&(g.phase=='train')].sort_values('pulse').aBN1.to_list()
        values['fast24']=values['fast12']+extra
        for block in [2,3]:values[f'cycle{block}']=g[(g.case=='h3')&(g.phase=='train')&(g.block==block)].sort_values('pulse').aBN1.to_list()
        tm={k:train_metrics(v) for k,v in values.items()}
        for k,v in tm.items():trains.append({'seed':seed,'case':k,**v})
        rec={};probes={}
        for case in ['fast12','slow12','fast24']:
            h=g[(g.case==case)&(g.phase=='recovery')].sort_values('rest_ms');probes[case]=h.aBN1.to_numpy()
            rec[case]=recovery_metrics(tm[case],h.rest_ms.to_numpy(),probes[case])
            for i,row in enumerate(h.itertuples()):profiles.append({'seed':seed,'case':case,'rest_ms':row.rest_ms,'aBN1':row.aBN1,'F':rec[case]['F'][i],
                             'relative_initial':rec[case]['relative_initial'][i],'initial':tm[case]['initial'],'late':tm[case]['late']})
        h3=h3_screen([tm['fast12'],tm['cycle2'],tm['cycle3']]);scores.append({'seed':seed,'hallmark':'H3',**h3})
        eligible=all(tm[k]['initial_usable'] and tm[k]['decrement'] and tm[k]['plateau'] and tm[k]['initial']>tm[k]['late'] for k in ['fast12','slow12'])
        indices=[spec['recovery_ms'].index(x) for x in [500.,1000.,2000.]]
        delta=float(np.median([rec['fast12']['F'][i]-rec['slow12']['F'][i] for i in indices])) if eligible else None
        earlier=strictly_earlier(rec['fast12']['half_lost'],rec['slow12']['half_lost'])
        reverse=strictly_earlier(rec['slow12']['half_lost'],rec['fast12']['half_lost'])
        abs_fast=strictly_earlier(rec['fast12']['eighty_initial'],rec['slow12']['eighty_initial'])
        abs_slow=strictly_earlier(rec['slow12']['eighty_initial'],rec['fast12']['eighty_initial'])
        h4={'seed':seed,'hallmark':'H4b','eligible':bool(eligible),'median_fraction_advantage':delta,
            'fast_half_interval':rec['fast12']['half_lost'],'slow_half_interval':rec['slow12']['half_lost'],
            'fast_80_interval':rec['fast12']['eighty_initial'],'slow_80_interval':rec['slow12']['eighty_initial'],
            'supported':bool(eligible and earlier and delta>=.1),
            'opposite_screen':bool(eligible and reverse and delta<=-.1),'absolute_80_high_faster':abs_fast,'absolute_80_low_faster':abs_slow}
        h4['normalization_conflict']=bool((h4['supported'] and abs_slow) or (h4['opposite_screen'] and abs_fast));scores.append(h4)
        deltaD=tm['fast12']['D']-tm['strong12']['D'];usable=tm['fast12']['initial_usable'] and tm['strong12']['initial_usable']
        scores.append({'seed':seed,'hallmark':'H5','eligible':bool(usable),'D_150':tm['fast12']['D'],'D_200':tm['strong12']['D'],
                       'weak_minus_strong_D':deltaD,'supported':bool(usable and deltaD>=.1-1e-12)})
        eligible=all(tm[k]['initial_usable'] and tm[k]['decrement'] and tm[k]['plateau'] and tm[k]['initial']>tm[k]['late'] for k in ['fast12','fast24'])
        lower=int(np.sum(probes['fast24']<=probes['fast12']-1))
        later=strictly_earlier(rec['fast12']['half_lost'],rec['fast24']['half_lost'])
        scores.append({'seed':seed,'hallmark':'H6','eligible':bool(eligible),'lower_probe_points':lower,'half_recovery_delayed':later,
                       'probe_differences_24_minus_12':(probes['fast24']-probes['fast12']).astype(int).tolist(),
                       'supported':bool(eligible and (lower>=2 or later))})
    return scores,pd.DataFrame(trains),pd.DataFrame(profiles)


def novel_scores(d,spec):
    scores=[]
    for seed in spec['seeds']:
        g=d[d.seed==seed]
        naive=g[g.phase=='naive_A'].iloc[0];sham=g[g.phase=='sham_A'].iloc[0]
        train=train_metrics(g[(g.case=='novel_train')&(g.phase=='train')].sort_values('pulse').aBN1)
        for B in spec['B_populations']:
            h=g[g.case==B].set_index('phase');b0=h.loc['naive_B'];bt=h.loc['trained_B']
            a0=h.loc['naive_after_B'];at=h.loc['trained_after_B'];blank=h.loc['blank_after_B']
            eligible=naive.aBN1>=5 and b0.aBN1>=5 and .5*naive.aBN1<=b0.aBN1<=2*naive.aBN1
            scores.append({'seed':seed,'hallmark':'H7','B':B,'eligible':bool(eligible),'A_naive':int(naive.aBN1),'A_sham':int(sham.aBN1),
                           'B_naive':int(b0.aBN1),'B_trained':int(bt.aBN1),'B_retention':float(bt.aBN1/b0.aBN1) if b0.aBN1 else None,
                           'supported':bool(eligible and sham.aBN1<=.5*naive.aBN1 and bt.aBN1>=.8*b0.aBN1)})
            gain=int(at.aBN1-sham.aBN1);naive_gain=int(a0.aBN1-naive.aBN1)
            eligible=train['initial_usable'] and train['decrement'] and sham.aBN1<naive.aBN1 and min(b0.noninput_spikes,bt.noninput_spikes)>=spec['B_min_noninput_spikes'] and blank.aBN1==0
            scores.append({'seed':seed,'hallmark':'H8','B':B,'eligible':bool(eligible),'A_naive':int(naive.aBN1),'A_sham':int(sham.aBN1),
                           'A_after_B':int(at.aBN1),'trained_gain':gain,'naive_gain':naive_gain,'gain_interaction':gain-naive_gain,
                           'B_naive_noninput_spikes':int(b0.noninput_spikes),'B_trained_noninput_spikes':int(bt.noninput_spikes),
                           'blank_aBN1':int(blank.aBN1),'supported':bool(eligible and gain>=max(2,.2*naive.aBN1))})
    return scores


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--main',type=Path);ap.add_argument('--novel',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    base.require(args.main is not None or args.novel is not None,'No input runs')
    spec=json.loads((HERE/'protocol.json').read_text());out=args.output.resolve();base.require(not out.exists(),'Output exists')
    provenance=[];scores=[];frames={};checks=[];signatures={};train=None;recovery=None
    for part,path in [('novel',args.novel),('main',args.main)]:
        if path is None:continue
        path=path.resolve();d,evidence,check,sig=audit(path,spec)
        base.require(evidence['part']==part,'Wrong run part')
        frames[part]=d;provenance.append(evidence);checks.append(check.assign(part=part));signatures[part]=sig
        if part=='main':
            s,train,recovery=main_scores(d,spec);scores+=s
            note=json.loads((HERE/'recovery_note_freeze.json').read_text());m=json.loads((path/'manifest.json').read_text())
            base.require(note['sha256']==base.sha(HERE/'RECOVERY_INTERPRETATION.md'),'Recovery note changed')
            base.require(datetime.fromisoformat(note['created_utc'])<datetime.fromisoformat(m['created_utc']),'Recovery note not prospective')
        else:scores+=novel_scores(d,spec)
    allchecks=pd.concat(checks,ignore_index=True);input_valid=bool(allchecks.matches_expected.all())
    paired_equivalence=signatures.get('main')==signatures.get('novel') if len(signatures)==2 else None
    groups={}
    for s in scores:
        key=s['hallmark']+(':'+s['B'] if 'B' in s else '')
        g=groups.setdefault(key,{'tested_realizations':0,'eligible':0,'supported':0})
        g['tested_realizations']+=1;g['eligible']+=int(s['eligible']);g['supported']+=int(s['supported'])
    for g in groups.values():g['consistent_support']=bool(input_valid and g['supported']>=spec['consistent_seeds'])
    h9=[b for b in spec['B_populations'] if groups.get('H8:'+b,{}).get('consistent_support',False)]
    report={'status':'completed_audit','created_utc':datetime.now(timezone.utc).isoformat(),'analyzer_sha256':base.sha(Path(__file__)),
            'metrics_sha256':base.sha(HERE/'metrics.py'),'protocol_sha256':base.sha(HERE/'PROTOCOL.md'),
            'provenance':provenance,'actual_input_sequences_verified':input_valid,'main_vs_B_interface_train_event_hashes_equal':paired_equivalence,
            'screens':scores,'groups':groups,'H9_eligible_B':h9,'H10':'Not tested: no long-term mechanism or validated long-term assay.',
            'interpretation':'Neural proxies in one fixed simulator. Operational screens are not universal biological criteria. H4b normalization conflicts must be reported.'}
    out.mkdir(parents=True,exist_ok=False)
    base.write_json(out/'report.json',report);pd.DataFrame(scores).to_csv(out/'screens.csv',index=False);allchecks.to_csv(out/'input_checks.csv',index=False)
    for part,d in frames.items():d.to_csv(out/f'{part}_responses.csv',index=False)
    if train is not None:train.to_csv(out/'training_metrics.csv',index=False);recovery.to_csv(out/'recovery_profiles.csv',index=False)
    print(json.dumps({'groups':groups,'input_valid':input_valid,'paired_event_equivalence':paired_equivalence,'H9_eligible_B':h9,'provenance':provenance},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
