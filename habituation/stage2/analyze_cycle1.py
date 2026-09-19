#!/usr/bin/env python3
"""Independent event-level audit and hypothesis scoring for cycle 1."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_experiment as base
pd,np=base.pd,base.np


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runs',type=Path,nargs='+',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    frames=[];provenance=[];event_maps={}
    for path in args.runs:
        path=path.resolve();m=json.loads((path/'manifest.json').read_text())
        base.require(m['status']=='completed','Incomplete cycle1 run')
        for name,digest in m['source_sha256'].items():
            source=path/'runner_snapshot.py' if name.endswith('/run_cycle1.py') else base.ROOT/name
            base.require(base.sha(source)==digest,'Changed source '+name)
        base.require(base.sha(path/'responses.csv')==m['responses_sha256'],'Changed response file')
        registered={f['file']:f['sha256'] for f in m['files']}
        cells=json.loads((path/'neuron_ids.json').read_text());inputs={int(x) for x in cells['input']}
        d=pd.read_csv(path/'responses.csv');frames.append(d)
        for row in d.itertuples():
            f=path/row.event_file;base.require(base.sha(f)==registered[f.name],'Changed raw events')
            e=pd.read_parquet(f)
            base.require(e.flywire_id.dtype==np.int64 and e.tick.dtype==np.int64,'Lost integer precision')
            base.require(not e.duplicated(['tick','flywire_id']).any(),'Duplicate events')
            base.require(((e.tick>=0)&(e.tick<3000)).all(),'Out of response window')
            base.require(len(e)==row.total_spikes,'Total mismatch')
            for cell,ident in cells['readouts'].items():base.require((e.flywire_id==int(ident)).sum()==getattr(row,cell),'Readout mismatch')
            sensory=e[e.flywire_id.isin(inputs)].reset_index(drop=True)
            base.require(len(sensory)==row.sensory_spikes,'Sensory mismatch')
            event_maps[(row.seed,row.phase,row.pulse)]=(e,sensory)
        provenance.append({'path':str(path.relative_to(base.ROOT)),'manifest_sha256':base.sha(path/'manifest.json'),'elapsed_seconds':m['elapsed_seconds']})
    d=pd.concat(frames,ignore_index=True)
    base.require(not d.duplicated(['seed','phase','pulse']).any(),'Duplicate rows')
    base.require(set(d.seed)==set(range(1701,1706)) and len(d)==90,'Incomplete seed/condition coverage')
    scores=[]
    for seed,g in d.groupby('seed'):
        train=g[g.phase=='train'].sort_values('pulse');base.require(list(train.pulse)==list(range(12)),'Incomplete train')
        other=g[g.phase!='train'].set_index('phase')
        expected={'naive_bypass','sham','resource_reset','fast_reset','both_reset','trained_bypass'}
        base.require(set(other.index)==expected,'Incomplete branches')
        initial=event_maps[(seed,'train',0)]
        for row in g.itertuples():
            if 'bypass' not in row.phase:pd.testing.assert_frame_equal(initial[1],event_maps[(seed,row.phase,row.pulse)][1])
        pd.testing.assert_frame_equal(initial[0],event_maps[(seed,'both_reset',-1)][0])
        naive=float(train.aBN1.iloc[0]);sham=float(other.loc['sham','aBN1']);res=float(other.loc['resource_reset','aBN1']);fast=float(other.loc['fast_reset','aBN1'])
        row={'seed':int(seed),'initial_aBN1':naive,'late_aBN1':float(train.aBN1.tail(3).mean()),'sham_aBN1':sham,
             'resource_reset_aBN1':res,'fast_reset_aBN1':fast,'resource_rescue_ratio':res/naive if naive else None,
             'resource_rescue_screen':bool(naive>0 and res>=.8*naive),'fast_reset_screen':bool(abs(fast-sham)<=1),
             'both_reset_full_events_equal':True,
             'bypass_full_events_equal':event_maps[(seed,'naive_bypass',-1)][0].equals(event_maps[(seed,'trained_bypass',-1)][0])}
        for cell in ['aBN1','aDN1','aDN2']:
            row['naive_bypass_'+cell]=int(other.loc['naive_bypass',cell]);row['trained_bypass_'+cell]=int(other.loc['trained_bypass',cell])
        scores.append(row)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    d.to_csv(out/'responses.csv',index=False);s=pd.DataFrame(scores);s.to_csv(out/'scores.csv',index=False)
    report={'cycle':1,'provenance':provenance,'raw_event_files_verified':len(d),'seeds':5,
            'resource_rescue_pass':int(s.resource_rescue_screen.sum()),'fast_reset_no_rescue_pass':int(s.fast_reset_screen.sum()),
            'both_reset_equivalence_pass':int(s.both_reset_full_events_equal.sum()),'bypass_equivalence_pass':int(s.bypass_full_events_equal.sum()),
            'means':{k:float(s[k].mean()) for k in ['initial_aBN1','sham_aBN1','resource_reset_aBN1','fast_reset_aBN1']},
            'conclusion_scope':'Within the specified STD simulator, not identification of a living-fly mechanism.'}
    base.write_json(out/'report.json',report);print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
