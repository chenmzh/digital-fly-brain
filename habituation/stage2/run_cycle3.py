#!/usr/bin/env python3
"""Prospective full-brain tests of pre-frozen low-dimensional forecasts."""
import argparse
import gc
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import run_experiment as base
from surrogates import expected_sensory
b2,np,pd=base.b2,base.np,base.pd


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--frozen',type=Path,default=HERE/'analysis/cycle2/frozen_models.json');ap.add_argument('--condition',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    frozen=args.frozen.resolve();f=json.loads(frozen.read_text());spec=f['spec']
    base.require(f['status']=='predictions_frozen_before_new_full_brain_runs','Forecasts not frozen')
    predpath=frozen.parent/'prospective_predictions.csv';base.require(base.sha(predpath)==f['prediction_sha256'],'Predictions changed')
    for path,digest in f['source_sha256'].items():base.require(base.sha(base.ROOT/path)==digest,'Frozen model/source changed: '+path)
    condition=next(x for x in f['selected_conditions'] if x['name']==args.condition)
    p=json.loads((HERE.parent/'protocols/main_v1.json').read_text())
    p.update(id='stage2-'+condition['name'],input_hz=condition['input_hz'],pulse_ms=condition['pulse_ms'],response_ms=condition['response_ms'],
             onset_intervals_ms=[condition['interval_ms']],n_pulses=condition['n_pulses'],recovery_ms=spec['recovery_ms'],seeds=spec['prospective_seeds'])
    base.validate_protocol(p)
    base.require(subprocess.check_output(['git','-C',str(base.UP),'rev-parse','HEAD'],text=True).strip()==base.COMMIT,'Wrong upstream')
    base.require(not subprocess.check_output(['git','-C',str(base.UP),'status','--porcelain'],text=True).strip(),'Dirty upstream')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'runner_snapshot.py').write_bytes(Path(__file__).read_bytes());base.write_json(out/'protocol.json',p)
    sources=[Path(__file__),HERE/'surrogates.py',HERE/'cycle3_implementation.md',HERE.parent/'run_experiment.py',frozen,predpath,base.UP/'model.py',base.COMP,base.CON]
    m={'status':'running','created_utc':datetime.now(timezone.utc).isoformat(),'forecast_created_utc':f['created_utc'],'condition':condition,
       'source_sha256':{str(x.relative_to(base.ROOT)):base.sha(x) for x in sources},'files':[],'completed_sequences':[]}
    base.write_json(out/'manifest.json',m)
    ids=pd.read_csv(base.COMP,index_col=0).index.to_numpy(dtype=np.int64);inputs=base.inputs_from_notebook(p['input_population'])
    base.write_json(out/'neuron_ids.json',{'input':[str(x) for x in inputs],'readouts':p['readouts']})
    rows=[];starttime=time.perf_counter()
    try:
        brain=base.Brain(p,'std',inputs,ids)
        for seed in p['seeds']:
            print('START',condition['name'],seed,flush=True)
            brain.net.restore('initial',restore_random_state=True)
            pattern=base.input_pattern(seed,len(inputs),p)
            np.savez_compressed(out/f'pattern_s{seed}.npz',input_index=pattern[0],tick=pattern[1])
            for k in range(p['n_pulses']):
                data=brain.pulse(pattern)
                rows.append({'condition':condition['name'],'model':'std','seed':seed,'phase':'train','pulse':k,'rest_ms':0,**data})
                if k<p['n_pulses']-1:brain.net.run((condition['interval_ms']-p['response_ms'])*b2.ms)
            path=out/f's{seed}_train.parquet';m['files'].append(brain.save_spikes(path))
            brain.net.store('trained');offset=int(brain.monitor.num_spikes)
            for rest in p['recovery_ms']:
                brain.net.restore('trained',restore_random_state=True);brain.net.run(rest*b2.ms)
                data=brain.pulse(pattern)
                rows.append({'condition':condition['name'],'model':'std','seed':seed,'phase':'recovery','pulse':-1,'rest_ms':rest,**data})
                path=out/f's{seed}_rest{int(rest)}.parquet';m['files'].append(brain.save_spikes(path,offset))
            pd.DataFrame(rows).to_csv(out/'responses.csv',index=False)
            m['completed_sequences'].append(seed);m['elapsed_seconds']=time.perf_counter()-starttime;base.write_json(out/'manifest.json',m)
            print('DONE',seed,'aBN1',[r['aBN1'] for r in rows if r['seed']==seed],flush=True)
        del brain;gc.collect()
        # Supplementary baseline, declared before the prospective experiments.
        # No repeated M0 sequence or behavior inference is implied by this probe.
        brain=base.Brain(p,'static',inputs,ids)
        for seed in p['seeds']:
            brain.net.restore('initial',restore_random_state=True);pattern=base.input_pattern(seed,len(inputs),p)
            data=brain.pulse(pattern)
            rows.append({'condition':condition['name'],'model':'static','seed':seed,'phase':'naive','pulse':0,'rest_ms':0,**data})
            path=out/f's{seed}_static_naive.parquet';m['files'].append(brain.save_spikes(path))
        pd.DataFrame(rows).to_csv(out/'responses.csv',index=False)
        m['status']='completed'
    except BaseException as e:
        m['status']='failed';m['error']=repr(e);pd.DataFrame(rows).to_csv(out/'partial_responses.csv',index=False);raise
    finally:
        m['elapsed_seconds']=time.perf_counter()-starttime;m['peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        if (out/'responses.csv').exists():m['responses_sha256']=base.sha(out/'responses.csv')
        base.write_json(out/'manifest.json',m)
    print('FINISHED',m['status'],m['elapsed_seconds'],flush=True)


if __name__=='__main__':main()
