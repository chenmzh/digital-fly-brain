#!/usr/bin/env python3
"""Fit low-dimensional simulator surrogates and freeze prospective predictions."""
import argparse
import itertools
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_experiment as base
from scipy.optimize import least_squares
np,pd=base.np,base.pd
HERE=Path(__file__).resolve().parent


def expected_sensory(pattern,n=70):
    last=np.full(n,-10000,dtype=int);events=[]
    for cell,tick in zip(*pattern):
        if tick>last[cell]+1:
            events.append((int(tick+1),int(cell)));last[cell]=tick
    return np.asarray(events,dtype=np.int64).reshape(-1,2)


def pattern_rate(seed,condition):
    p=json.loads((HERE.parent/'protocols/main_v1.json').read_text())
    p.update(pulse_ms=condition['pulse_ms'],input_hz=condition['input_hz'])
    pattern=base.input_pattern(seed,70,p)
    count=len(expected_sensory(pattern))
    return count/(70*condition['pulse_ms']/1000),count


def silence(state,t,tau,kind):
    return 1-(1-state)*np.exp(-t/tau) if kind=='resource' else state*np.exp(-t/tau)


def pulse_state(state,f,p,tau,U,kind):
    if kind=='resource':
        rate=1/tau+U*f;equilibrium=(1/tau)/rate
    else:
        rate=1/tau;equilibrium=f/150
    e=np.exp(-rate*p)
    avg=equilibrium+(state-equilibrium)*(-np.expm1(-rate*p))/(rate*p)
    end=equilibrium+(state-equilibrium)*e
    feature=np.array([f/150*avg,-1.0]) if kind=='resource' else np.array([f/150,-avg])
    return feature,end


def episode_features(kind,condition,f,spec):
    p=condition['pulse_ms']/1000;T=condition['interval_ms']/1000
    tau=spec['state_tau_s'];U=spec['std_U'];state=1. if kind=='resource' else 0.
    rows=[]
    for k in range(condition['n_pulses']):
        feature,end=pulse_state(state,f,p,tau,U,kind)
        rows.append({'phase':'train','pulse':k,'rest_ms':0.,'features':feature,'scale':p/spec['reference_pulse_s']})
        state=silence(end,T-p,tau,kind)
    for rest in spec['recovery_ms']:
        at_probe=silence(end,(condition['response_ms']-condition['pulse_ms']+rest)/1000,tau,kind)
        feature,_=pulse_state(at_probe,f,p,tau,U,kind)
        rows.append({'phase':'recovery','pulse':-1,'rest_ms':float(rest),'features':feature,'scale':p/spec['reference_pulse_s']})
    return rows


def predict(features,scales,params):
    return np.maximum(0,np.asarray(features)@np.asarray(params))*np.asarray(scales)


def metrics(actual,pred):
    delta=np.asarray(pred)-np.asarray(actual)
    return {'n':len(delta),'mae':float(np.abs(delta).mean()),'rmse':float(np.sqrt((delta**2).mean())),'bias':float(delta.mean())}


def validate_old_interface():
    path=HERE.parent/'results/main_v1'
    ids=np.array([int(x) for x in json.loads((path/'neuron_ids.json').read_text())['input']])
    for seed in range(1701,1706):
        z=np.load(path/f'pattern_seed{seed}.npz');expected=expected_sensory((z['input_index'],z['tick']))
        expected=pd.DataFrame({'tick':expected[:,0],'flywire_id':ids[expected[:,1]]}).sort_values(['tick','flywire_id']).reset_index(drop=True)
        actual=pd.read_parquet(path/f'static_s{seed}_T500_train.parquet')
        actual=actual[(actual.t_s<.3)&actual.flywire_id.isin(ids)]
        actual=pd.DataFrame({'tick':np.rint(actual.t_s.values/.0001).astype(np.int64),'flywire_id':actual.flywire_id.values}).sort_values(['tick','flywire_id']).reset_index(drop=True)
        pd.testing.assert_frame_equal(expected,actual)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    spec=json.loads((HERE/'cycle2_spec.json').read_text())
    validate_old_interface()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'surrogates_snapshot.py').write_bytes(Path(__file__).read_bytes())
    old=pd.read_csv(HERE.parent/'analysis/responses.csv');old=old[old.model=='std'].copy()
    fitmask=(old.interval_ms==500)&(old.phase=='train')
    fitted={};old_predictions=[]
    for kind in spec['surrogates']:
        features=[];scales=[]
        oldspec=dict(spec,recovery_ms=[2000.,10000.])
        for row in old.itertuples():
            cond=dict(input_hz=150.,pulse_ms=200.,response_ms=300.,interval_ms=float(row.interval_ms),n_pulses=12)
            f,_=pattern_rate(row.seed,cond)
            rows=episode_features(kind,cond,f,oldspec)
            item=next(x for x in rows if x['phase']==row.phase and x['pulse']==row.pulse and x['rest_ms']==row.rest_ms)
            features.append(item['features']);scales.append(item['scale'])
        features=np.asarray(features);scales=np.asarray(scales);y=old.aBN1.to_numpy()
        candidates=[]
        for a,b in itertools.product(spec['fit_initial_A'],spec['fit_initial_B']):
            result=least_squares(lambda v:predict(features[fitmask],scales[fitmask],v)-y[fitmask],x0=[a,b],bounds=spec['readout_parameter_bounds'],max_nfev=2000)
            candidates.append((float(np.sum(result.fun**2)),result.x))
        loss,params=min(candidates,key=lambda x:x[0]);pred=predict(features,scales,params)
        fitted[kind]={'A':float(params[0]),'B':float(params[1]),'sse_fit':loss,
                      'fit_metrics':metrics(y[fitmask],pred[fitmask]),'retrospective_metrics':metrics(y[~fitmask],pred[~fitmask])}
        for row,value in zip(old.to_dict('records'),pred):
            old_predictions.append({**{k:row[k] for k in ['seed','interval_ms','phase','pulse','rest_ms','aBN1']},'surrogate':kind,'prediction':float(value),'partition':'fit' if row['interval_ms']==500 and row['phase']=='train' else 'retrospective'})
    pd.DataFrame(old_predictions).to_csv(out/'old_predictions.csv',index=False)
    design=[];prediction_records={}
    for hz,pulse,gap in itertools.product(spec['candidate_input_hz'],spec['candidate_pulse_ms'],spec['candidate_silent_gap_ms']):
        cond={'name':f'f{int(hz)}_p{int(pulse)}_gap{int(gap)}','input_hz':hz,'pulse_ms':pulse,'response_ms':pulse+spec['response_tail_ms'],'interval_ms':pulse+gap,'n_pulses':spec['candidate_n_pulses']}
        predictions=forecast_condition(cond,spec,fitted)
        score=float(np.sqrt(np.mean([(r['resource']-r['accumulator'])**2 for r in predictions])))
        design.append({**cond,'disagreement_rmse':score});prediction_records[cond['name']]=predictions
    design.sort(key=lambda x:(-x['disagreement_rmse'],x['name']))
    first=design[0]
    second=next(x for x in design[1:] if (x['input_hz'],x['pulse_ms'])!=(first['input_hz'],first['pulse_ms']))
    selected=[dict(spec['control']),first,second]
    predictions=[]
    for cond in selected:predictions+=forecast_condition(cond,spec,fitted)
    pd.DataFrame(predictions).to_csv(out/'prospective_predictions.csv',index=False)
    pd.DataFrame(design).to_csv(out/'candidate_designs.csv',index=False)
    payload={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'predictions_frozen_before_new_full_brain_runs',
             'spec':spec,'models':fitted,'selected_conditions':selected,
             'source_sha256':{str(x.relative_to(base.ROOT)):base.sha(x) for x in [Path(__file__),HERE/'cycle2_spec.json',HERE/'PROTOCOL.md',HERE.parent/'analysis/responses.csv',HERE.parent/'run_experiment.py']},
             'prediction_sha256':base.sha(out/'prospective_predictions.csv'),
             'notes':['Retrospective checks are not blind because old summaries were known.','Two scalar surrogates, not new full-brain biological mechanisms.','New output data must not be used to refit these models.']}
    base.write_json(out/'frozen_models.json',payload)
    print(json.dumps({'models':fitted,'selected':selected,'forecast_windows':len(predictions)},indent=2))


def forecast_condition(cond,spec,fitted):
    records=[]
    for seed in spec['prospective_seeds']:
        f,count=pattern_rate(seed,cond)
        episodes={kind:episode_features(kind,cond,f,spec) for kind in fitted}
        for index,template in enumerate(episodes['resource']):
            row={'condition':cond['name'],'seed':seed,'phase':template['phase'],'pulse':template['pulse'],'rest_ms':template['rest_ms'],
                 'expected_sensory_spikes':count,'effective_input_hz':f}
            for kind,parameters in fitted.items():
                e=episodes[kind][index]
                row[kind]=float(predict([e['features']],[e['scale']],[parameters['A'],parameters['B']])[0])
            records.append(row)
    return records


if __name__=='__main__':main()
