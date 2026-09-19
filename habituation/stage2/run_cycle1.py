#!/usr/bin/env python3
"""Causal state intervention on the existing full-brain STD model."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_experiment as base
b2, np, pd = base.b2, base.np, base.pd


def relative_events(brain, start, onset):
    dt = float(brain.p['dt_ms'])/1000
    ids = brain.ids[np.asarray(brain.monitor.i[start:])]
    ticks = np.rint(np.asarray(brain.monitor.t[start:]/b2.second)/dt).astype(np.int64)-round(onset/dt)
    return pd.DataFrame({'tick':ticks, 'flywire_id':ids}).sort_values(['tick','flywire_id']).reset_index(drop=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--seeds',nargs='+',type=int,default=[1701,1702,1703,1704,1705])
    args=ap.parse_args()
    p=json.loads((HERE.parent/'protocols/main_v1.json').read_text())
    base.validate_protocol(p)
    base.require(set(args.seeds).issubset(p['seeds']) and len(args.seeds)==len(set(args.seeds)), 'Invalid seed subset')
    base.require(subprocess.check_output(['git','-C',str(base.UP),'rev-parse','HEAD'],text=True).strip()==base.COMMIT,'Wrong upstream')
    base.require(not subprocess.check_output(['git','-C',str(base.UP),'status','--porcelain'],text=True).strip(),'Dirty upstream')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    sources=[Path(__file__),HERE/'PROTOCOL.md',HERE.parent/'run_experiment.py',HERE.parent/'protocols/main_v1.json',base.UP/'model.py',base.COMP,base.CON]
    m={'status':'running','created_utc':datetime.now(timezone.utc).isoformat(),'seeds':args.seeds,
       'scope':'Within-model causal state interventions, not biological dishabituation.',
       'source_sha256':{str(x.relative_to(base.ROOT)):base.sha(x) for x in sources},'files':[],'completed_seeds':[]}
    base.write_json(out/'manifest.json',m)
    (out/'runner_snapshot.py').write_bytes(Path(__file__).read_bytes())
    base.write_json(out/'protocol.json',p)
    ids=pd.read_csv(base.COMP,index_col=0).index.to_numpy(dtype=np.int64)
    inputs=base.inputs_from_notebook(p['input_population'])
    base.write_json(out/'neuron_ids.json',{'input':[str(x) for x in inputs],'readouts':p['readouts']})
    started=time.perf_counter(); rows=[]
    try:
        brain=base.Brain(p,'std',inputs,ids)
        bypass=b2.SpikeGeneratorGroup(1,[],[]*b2.ms,name='bypass_source')
        bypass_syn=b2.Synapses(bypass,brain.neu,on_pre='v_post += drive',name='bypass_inject',
            namespace={'drive':base.upstream.default_params['w_syn']*base.upstream.default_params['f_poi']})
        bypass_syn.connect(i=0,j=brain.read_ix['aBN1'])
        brain.net.add(bypass,bypass_syn)
        brain.net.store('initial')
        fast_initial={key:brain.neu.variables[key].get_value().copy() for key in ['v','g','lastspike','not_refractory']}
        m['network']={'neurons':len(brain.neu),'anatomical_edges':len(brain.syn),'plastic_edges':brain.replaced_edges}
        for seed in args.seeds:
            print('START seed',seed,flush=True)
            pattern=base.input_pattern(seed,len(inputs),p)
            np.savez_compressed(out/f'pattern_{seed}.npz',input_index=pattern[0],tick=pattern[1])
            brain.net.restore('initial',restore_random_state=True)
            bypass.set_spikes(np.zeros(10,dtype=int),np.arange(10)*20*b2.ms,sorted=True)
            start=int(brain.monitor.num_spikes);onset=float(brain.net.t/b2.second)
            data=brain.pulse((np.array([],dtype=int),np.array([],dtype=int)))
            naive_bypass=relative_events(brain,start,onset)
            path=out/f's{seed}_naive_bypass.parquet';naive_bypass.to_parquet(path,index=False)
            m['files'].append({'file':path.name,'sha256':base.sha(path)})
            rows.append({'seed':seed,'phase':'naive_bypass','pulse':-1,'event_file':path.name,**data})
            brain.net.restore('initial',restore_random_state=True)
            # Brian2 2.5.1 restores dynamic arrays but not all set_spikes caches.
            # Explicitly clear the unused generator after restoring an empty snapshot.
            bypass.set_spikes(np.array([],dtype=int),np.array([])*b2.ms,sorted=True)
            initial_events=None
            for pulse in range(12):
                start=int(brain.monitor.num_spikes);onset=float(brain.net.t/b2.second)
                data=brain.pulse(pattern)
                events=relative_events(brain,start,onset)
                if pulse==0: initial_events=events.copy()
                path=out/f's{seed}_train{pulse:02}.parquet';events.to_parquet(path,index=False)
                m['files'].append({'file':path.name,'sha256':base.sha(path)})
                rows.append({'seed':seed,'phase':'train','pulse':pulse,'event_file':path.name,**data})
                before=int(brain.monitor.num_spikes)
                brain.net.run(200*b2.ms)
                base.require(int(brain.monitor.num_spikes)==before,'Unexpected gap spikes; intervention assumptions need review')
            brain.net.store('trained')
            base.require(abs(float(brain.net.t/b2.second)-6)<1e-9,'Wrong branch time')
            for branch in ['sham','resource_reset','fast_reset','both_reset','trained_bypass']:
                brain.net.restore('trained',restore_random_state=True)
                bypass.set_spikes(np.array([],dtype=int),np.array([])*b2.ms,sorted=True)
                if branch in ['resource_reset','both_reset']:
                    brain.plastic.x=1
                    brain.plastic.lastupdate=brain.net.t
                if branch in ['fast_reset','both_reset']:
                    for key,value in fast_initial.items():brain.neu.variables[key].set_value(value)
                probe_pattern=pattern
                if branch=='trained_bypass':
                    bypass.set_spikes(np.zeros(10,dtype=int),brain.net.t+np.arange(10)*20*b2.ms,sorted=True)
                    probe_pattern=(np.array([],dtype=int),np.array([],dtype=int))
                start=int(brain.monitor.num_spikes);onset=float(brain.net.t/b2.second)
                data=brain.pulse(probe_pattern)
                events=relative_events(brain,start,onset)
                path=out/f's{seed}_{branch}.parquet';events.to_parquet(path,index=False)
                m['files'].append({'file':path.name,'sha256':base.sha(path)})
                row={'seed':seed,'phase':branch,'pulse':-1,'event_file':path.name,**data}
                if branch=='both_reset':
                    # This is an implementation/time-translation gate, not a hypothesis success gate.
                    pd.testing.assert_frame_equal(initial_events,events)
                    row['both_reset_full_event_equivalence']=True
                if branch=='trained_bypass':row['bypass_full_event_equivalence']=naive_bypass.equals(events)
                rows.append(row)
            pd.DataFrame(rows).to_csv(out/'responses.csv',index=False)
            m['completed_seeds'].append(seed)
            m['elapsed_seconds']=time.perf_counter()-started
            base.write_json(out/'manifest.json',m)
            print('DONE',seed,[(r['phase'],r['aBN1'],r['aDN1'],r['aDN2']) for r in rows if r['seed']==seed and r['phase']!='train'],flush=True)
        m['status']='completed'
    except BaseException as e:
        m['status']='failed';m['error']=repr(e)
        pd.DataFrame(rows).to_csv(out/'partial_responses.csv',index=False)
        raise
    finally:
        m['elapsed_seconds']=time.perf_counter()-started
        m['peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        if (out/'responses.csv').exists():m['responses_sha256']=base.sha(out/'responses.csv')
        base.write_json(out/'manifest.json',m)
    print('FINISHED',m['elapsed_seconds'],flush=True)


if __name__=='__main__':main()
