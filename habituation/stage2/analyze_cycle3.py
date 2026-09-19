#!/usr/bin/env python3
"""Audit prospective events and score frozen forecasts without refitting."""
import argparse
import json
from pathlib import Path
import sys
from datetime import datetime
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import run_experiment as base
from surrogates import expected_sensory,metrics
pd,np=base.pd,base.np


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runs',nargs='+',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    frozenpath=HERE/'analysis/cycle2/frozen_models.json';f=json.loads(frozenpath.read_text())
    predpath=frozenpath.parent/'prospective_predictions.csv';base.require(base.sha(predpath)==f['prediction_sha256'],'Frozen forecast changed')
    pred=pd.read_csv(predpath);frames=[];provenance=[];files_checked=0;quiet_spikes=0
    for root in args.runs:
        root=root.resolve();m=json.loads((root/'manifest.json').read_text())
        base.require(m['status']=='completed','Incomplete prospective run')
        base.require(datetime.fromisoformat(m['created_utc'])>datetime.fromisoformat(f['created_utc']),'Forecast chronology violation')
        for name,digest in m['source_sha256'].items():
            source=root/'runner_snapshot.py' if name.endswith('/run_cycle3.py') else base.ROOT/name
            base.require(base.sha(source)==digest,'Source changed: '+name)
        base.require(base.sha(root/'responses.csv')==m['responses_sha256'],'Responses changed')
        registry={r['file']:r['sha256'] for r in m['files']}
        p=json.loads((root/'protocol.json').read_text());dt=p['dt_ms']/1000
        name=m['condition']['name'];cond=next(c for c in f['selected_conditions'] if c['name']==name)
        for key in ['pulse_ms','response_ms','input_hz','n_pulses']:base.require(p[key]==cond[key],'Protocol drift')
        base.require(p['seeds']==f['spec']['prospective_seeds'] and p['recovery_ms']==f['spec']['recovery_ms'],'Protocol drift')
        cells=json.loads((root/'neuron_ids.json').read_text());ids=np.array([int(x) for x in cells['input']],dtype=np.int64)
        d=pd.read_csv(root/'responses.csv');base.require(set(d.condition)=={name},'Condition label mismatch')
        frames.append(d)
        for seed in p['seeds']:
            expected_pattern=base.input_pattern(seed,70,p);saved=np.load(root/f'pattern_s{seed}.npz')
            np.testing.assert_array_equal(expected_pattern[0],saved['input_index']);np.testing.assert_array_equal(expected_pattern[1],saved['tick'])
            expected=expected_sensory(expected_pattern)
            expected=pd.DataFrame({'tick':expected[:,0],'flywire_id':ids[expected[:,1]]}).sort_values(['tick','flywire_id']).reset_index(drop=True)
            forecast=pred[(pred.condition==name)&(pred.seed==seed)]
            base.require((forecast.expected_sensory_spikes==len(expected)).all(),'Frozen input forecast mismatch')
            groups=[(f's{seed}_train.parquet',d[(d.seed==seed)&(d.model=='std')&(d.phase=='train')])]
            groups += [(f's{seed}_rest{int(rest)}.parquet',d[(d.seed==seed)&(d.model=='std')&(d.phase=='recovery')&(d.rest_ms==rest)]) for rest in p['recovery_ms']]
            groups += [(f's{seed}_static_naive.parquet',d[(d.seed==seed)&(d.model=='static')])]
            base.require(list(groups[0][1].pulse)==list(range(p['n_pulses'])),'Incomplete training')
            for filename,selected in groups:
                base.require(len(selected)==(p['n_pulses'] if filename.endswith('_train.parquet') else 1),'Incomplete response group')
                path=root/filename;base.require(base.sha(path)==registry[filename],'Raw file changed')
                e=pd.read_parquet(path);base.require(e.flywire_id.dtype==np.int64,'ID precision')
                ticks=np.rint(e.t_s.values/dt).astype(np.int64)
                base.require(np.allclose(ticks,e.t_s.values/dt,rtol=0,atol=1e-7),'Off-grid events')
                base.require(not e.duplicated(['t_s','flywire_id']).any(),'Duplicate spikes')
                inside=np.zeros(len(e),dtype=bool)
                for row in selected.itertuples():
                    onset=0. if row.model=='static' else (row.pulse*cond['interval_ms']/1000 if row.phase=='train' else ((p['n_pulses']-1)*cond['interval_ms']+p['response_ms']+row.rest_ms)/1000)
                    base.require(abs(row.onset_s-onset)<1e-8,'Incorrect onset')
                    t0=round(onset/dt);mask=(ticks>=t0)&(ticks<t0+round(p['response_ms']/p['dt_ms']));inside|=mask
                    events=e[mask];base.require(len(events)==row.total_spikes,'Total count mismatch')
                    for cell,ident in cells['readouts'].items():base.require((events.flywire_id==int(ident)).sum()==getattr(row,cell),'Readout mismatch')
                    sensory=events.flywire_id.isin(ids).values
                    actual=pd.DataFrame({'tick':ticks[mask][sensory]-t0,'flywire_id':events.flywire_id.values[sensory]}).sort_values(['tick','flywire_id']).reset_index(drop=True)
                    pd.testing.assert_frame_equal(expected,actual)
                    base.require(len(actual)==row.sensory_spikes and row.input_events==len(expected_pattern[0]),'Input count mismatch')
                    base.require(0<=row.resource_before<=1+1e-12 and 0<=row.resource_after<=1+1e-12,'Resource out of bounds')
                quiet_spikes+=int((~inside).sum());files_checked+=1
        provenance.append({'path':str(root.relative_to(base.ROOT)),'manifest_sha256':base.sha(root/'manifest.json'),'elapsed_seconds':m['elapsed_seconds'],'peak_rss_mib':m['peak_rss_mib']})
    d=pd.concat(frames,ignore_index=True)
    keys=['condition','seed','phase','pulse','rest_ms']
    base.require(not d.duplicated(['model']+keys).any(),'Duplicate responses')
    base.require(set(d.condition)=={c['name'] for c in f['selected_conditions']},'Missing design')
    joined=pred.merge(d[d.model=='std'],on=keys,how='outer',validate='one_to_one',indicator=True)
    base.require((joined['_merge']=='both').all() and len(joined)==102,'Forecast/outcome coverage mismatch')
    base.require(len(d[d.model=='static'])==9,'Missing supplementary baselines')
    joined=joined.drop(columns='_merge')
    rows=[];byseed=[]
    for condition,g in joined.groupby('condition'):
        for kind in ['resource','accumulator']:
            score=metrics(g.aBN1,g[kind]);rows.append({'condition':condition,'surrogate':kind,**score,'mae_screen':score['mae']<=f['spec']['evaluation']['per_condition_mae_threshold']})
            for (seed,phase),h in g.groupby(['seed','phase']):byseed.append({'condition':condition,'seed':int(seed),'phase':phase,'surrogate':kind,**metrics(h.aBN1,h[kind])})
    # Post-hoc diagnostic: added after viewing the first high-input trace.
    # It is not a preregistered score, a significance test, or a fitting target.
    rebounds=[]
    for (condition,seed),g in joined[joined.phase=='train'].groupby(['condition','seed']):
        g=g.sort_values('pulse').reset_index(drop=True)
        changes=np.diff(g.aBN1.to_numpy());i=int(np.argmax(changes))
        rebounds.append({'condition':condition,'seed':int(seed),'max_upward_step':float(max(0,changes[i])),
                         'from_stimulus':int(g.pulse.iloc[i])+1,'to_stimulus':int(g.pulse.iloc[i+1])+1,
                         'response_before':int(g.aBN1.iloc[i]),'response_after':int(g.aBN1.iloc[i+1]),
                         'resource_state_change':float(g.resource_before.iloc[i+1]-g.resource_before.iloc[i]),
                         'resource_prediction_change':float(g.resource.iloc[i+1]-g.resource.iloc[i]),
                         'accumulator_prediction_change':float(g.accumulator.iloc[i+1]-g.accumulator.iloc[i])})
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    pd.DataFrame(rebounds).to_csv(out/'exploratory_rebounds.csv',index=False)
    joined.to_csv(out/'forecast_outcomes.csv',index=False);d.to_csv(out/'responses.csv',index=False)
    pd.DataFrame(rows).to_csv(out/'scores_by_condition.csv',index=False);pd.DataFrame(byseed).to_csv(out/'scores_by_seed_phase.csv',index=False)
    report={'cycle':3,'frozen_models_sha256':base.sha(frozenpath),'frozen_predictions_sha256':base.sha(predpath),'provenance':provenance,
            'audit':{'prospective_std_windows':len(joined),'supplementary_static_windows':9,'raw_event_files_verified':files_checked,
                     'input_interface_event_prediction_verified':True,'forecast_precedes_all_simulation_runs':True,'outside_response_window_spikes':quiet_spikes},
            'scores':rows,'aggregate_scores':{k:metrics(joined.aBN1,joined[k]) for k in ['resource','accumulator']},
            'exploratory_rebounds':rebounds,
            'exploratory_note':'Post-hoc after first high-input trace; not used for fitting, design selection or primary pass/fail.',
            'interpretation_limits':['No refitting on prospective data.','Active-design sample is not a random sample of all stimulation regimes.','Simulator surrogate comparison is not living-fly mechanism identification.']}
    base.write_json(out/'report.json',report);print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
