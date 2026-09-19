#!/usr/bin/env python3
"""Frozen hallmark experiments on full M1; no fitting or resource resets."""
import argparse
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
b2,np,pd=base.b2,base.np,base.pd
EMPTY=(np.array([],dtype=int),np.array([],dtype=int))


class Experiment:
    def __init__(self,part,out):
        self.started=time.perf_counter();self.part=part;self.out=out;self.rows=[];self.seed=None
        self.spec=json.loads((HERE/'protocol.json').read_text())
        self.p=json.loads((HERE.parent/'protocols/main_v1.json').read_text())
        self.p.update(seeds=self.spec['seeds'],recovery_ms=self.spec['recovery_ms'],onset_intervals_ms=[self.spec['fast_interval_ms'],self.spec['slow_interval_ms']])
        for key in ['dt_ms','pulse_ms','response_ms']:base.require(self.p[key]==self.spec[key],'Interface protocol drift: '+key)
        base.require(self.spec['n_train']==12 and self.spec['n_extended']==24 and self.spec['n_cycles']==3 and self.spec['reference_hz']==150.,'This frozen runner requires the declared design')
        base.validate_protocol(self.p)
        base.require(subprocess.check_output(['git','-C',str(base.UP),'rev-parse','HEAD'],text=True).strip()==base.COMMIT,'Wrong upstream')
        base.require(not subprocess.check_output(['git','-C',str(base.UP),'status','--porcelain'],text=True).strip(),'Dirty upstream')
        out.mkdir(parents=True,exist_ok=False)
        (out/'runner_snapshot.py').write_bytes(Path(__file__).read_bytes())
        base.write_json(out/'protocol.json',self.spec)
        sources=[Path(__file__),HERE/'PROTOCOL.md',HERE/'protocol.json',HERE.parent/'run_experiment.py',HERE.parent/'protocols/main_v1.json',base.UP/'model.py',base.UP/'figures.ipynb',base.COMP,base.CON]
        self.manifest={'status':'running','part':part,'created_utc':datetime.now(timezone.utc).isoformat(),
                       'source_sha256':{str(p.relative_to(base.ROOT)):base.sha(p) for p in sources},'files':[],'completed_seeds':[]}
        base.write_json(out/'manifest.json',self.manifest)
        self.ids=pd.read_csv(base.COMP,index_col=0).index.to_numpy(dtype=np.int64)
        self.populations={'A':base.inputs_from_notebook('neu_JON_CE')}
        if part=='novel':
            for label in self.spec['B_populations']:self.populations[label]=base.inputs_from_notebook(label)
        allids=[x for group in self.populations.values() for x in group]
        base.require(len(allids)==len(set(allids)),'Overlapping sensory populations')
        self.input_union=set(allids)
        base.write_json(out/'neuron_ids.json',{'inputs':{k:[str(x) for x in v] for k,v in self.populations.items()},'readouts':self.p['readouts']})
        self.brain=base.Brain(self.p,'std',self.populations['A'],self.ids)
        self.bsource=None;self.offsets={}
        if part=='novel':
            mapping={int(x):i for i,x in enumerate(self.ids)};bids=[]
            for name,group in self.populations.items():
                if name=='A':continue
                self.offsets[name]=len(bids);bids+=group
            indices=np.array([mapping[x] for x in bids]);self.brain.neu.rfc[indices]=0*b2.ms
            self.bsource=b2.SpikeGeneratorGroup(len(bids),[],[]*b2.ms,name='hallmark_B_source')
            self.bsyn=b2.Synapses(self.bsource,self.brain.neu,on_pre='v_post += drive',name='hallmark_B_inject',
                namespace={'drive':base.upstream.default_params['w_syn']*base.upstream.default_params['f_poi']})
            self.bsyn.connect(i=np.arange(len(bids)),j=indices)
            self.brain.net.add(self.bsource,self.bsyn);self.brain.net.store('initial')
        self.manifest['network']={'neurons':len(self.brain.neu),'original_edges':len(self.brain.syn),'plastic_edges':self.brain.replaced_edges}
        self.patterns={}
        self.checkpoint()

    def restore(self,name):
        self.brain.net.restore(name,restore_random_state=True)
        self.brain.source.set_spikes(EMPTY[0],EMPTY[1]*b2.ms,sorted=True)
        if self.bsource is not None:self.bsource.set_spikes(EMPTY[0],EMPTY[1]*b2.ms,sorted=True)

    def prepare(self,seed):
        self.seed=seed;self.patterns={}
        for label,ids in self.populations.items():
            rates=[150.,200.] if label=='A' else [150.]
            for hz in rates:
                pat=base.input_pattern(seed,len(ids),dict(self.p,input_hz=hz))
                key=(label,hz);self.patterns[key]=pat
                path=self.out/f'pattern_s{seed}_{label}_{int(hz)}.npz'
                np.savez_compressed(path,input_index=pat[0],tick=pat[1])
                self.manifest['files'].append({'file':path.name,'sha256':base.sha(path)})

    def record(self,duration_ms,kind,case,phase,block=0,pulse=-1,rest_ms=0,label='blank',hz=150.):
        base.require(time.perf_counter()-self.started<self.spec['wall_budget_minutes']*60,'Wall budget exhausted')
        brain=self.brain;onset=float(brain.net.t/b2.second);start=int(brain.monitor.num_spikes)
        before=brain.resource_mean();pattern=EMPTY if label=='blank' else self.patterns[(label,hz)]
        if self.bsource is not None:self.bsource.set_spikes(EMPTY[0],EMPTY[1]*b2.ms,sorted=True)
        if kind=='response':
            if label in self.offsets:
                self.bsource.set_spikes(pattern[0]+self.offsets[label],brain.net.t+pattern[1]*self.p['dt_ms']*b2.ms,sorted=True)
                brain.pulse(EMPTY)
            else:brain.pulse(pattern)
        else:
            brain.source.set_spikes(EMPTY[0],EMPTY[1]*b2.ms,sorted=True)
            brain.net.run(duration_ms*b2.ms)
        ticks=np.rint(np.asarray(brain.monitor.t[start:]/b2.second)/(self.p['dt_ms']/1000)).astype(np.int64)-round(onset/(self.p['dt_ms']/1000))
        e=pd.DataFrame({'tick':ticks,'flywire_id':self.ids[np.asarray(brain.monitor.i[start:])]})
        e=e.sort_values(['tick','flywire_id']).reset_index(drop=True)
        filename=f'events_{len(self.rows):05d}.parquet';path=self.out/filename;e.to_parquet(path,index=False,compression='brotli')
        self.manifest['files'].append({'file':filename,'sha256':base.sha(path),'events':len(e)})
        row={'seed':self.seed,'kind':kind,'case':case,'phase':phase,'block':block,'pulse':pulse,'rest_ms':rest_ms,
             'label':label,'input_hz':hz if label!='blank' else 0.,'onset_s':onset,'duration_ms':duration_ms,
             'input_events':len(pattern[0]),'stimulus_spikes':int(e.flywire_id.isin(self.populations.get(label,[])).sum()),
             'sensory_A':int(e.flywire_id.isin(self.populations['A']).sum()),'total_spikes':len(e),
             'noninput_spikes':int((~e.flywire_id.isin(self.input_union)).sum()),
             'resource_before':before,'resource_after':brain.resource_mean(),'event_file':filename}
        for name,ident in self.p['readouts'].items():row[name]=int((e.flywire_id==int(ident)).sum())
        self.rows.append(row)
        return row

    def quiet(self,ms,case,phase,**kwargs):
        return self.record(ms,'quiet',case,phase,**kwargs)

    def pulse(self,case,phase,label='A',hz=150.,**kwargs):
        return self.record(self.spec['response_ms'],'response',case,phase,label=label,hz=hz,**kwargs)

    def train(self,case,interval_ms,block=1,start=0,end=12,hz=150.,initial_gap=False):
        for k in range(start,end):
            if k>start or initial_gap:self.quiet(interval_ms-self.spec['response_ms'],case,'gap',block=block,pulse=k)
            self.pulse(case,'train',block=block,pulse=k,hz=hz)

    def recovery(self,state,case):
        for rest in self.spec['recovery_ms']:
            self.restore(state);self.quiet(rest,case,'rest',rest_ms=rest)
            self.pulse(case,'recovery',rest_ms=rest)

    def main_seed(self):
        s=self.spec
        self.restore('initial');self.train('fast12',s['fast_interval_ms']);self.brain.net.store('base12')
        self.recovery('base12','fast12')
        self.restore('base12')
        for block in [2,3]:
            self.quiet(s['between_cycles_ms'],'h3','cycle_rest',block=block)
            self.train('h3',s['fast_interval_ms'],block=block)
        self.restore('base12');self.train('fast24',s['fast_interval_ms'],start=12,end=24,initial_gap=True)
        self.brain.net.store('trained');self.recovery('trained','fast24')
        self.restore('initial');self.train('slow12',s['slow_interval_ms']);self.brain.net.store('trained')
        self.recovery('trained','slow12')
        self.restore('initial');self.train('strong12',s['fast_interval_ms'],hz=s['strong_hz'])

    def novel_seed(self):
        s=self.spec;wait_after=s['B_wait_after_ms'];wait_before=s['B_wait_before_ms']
        self.restore('initial');self.quiet(s['response_ms']+wait_after,'novel','naive_wait')
        self.pulse('novel','naive_A')
        for B in s['B_populations']:
            self.restore('initial');self.pulse(B,'naive_B',label=B);self.brain.net.store('after_B')
            self.quiet(wait_after,B,'post_B_gap');self.pulse(B,'naive_after_B')
            self.restore('after_B');self.quiet(wait_after,B,'blank_gap');self.pulse(B,'blank_after_B',label='blank')
        self.restore('initial');self.train('novel_train',s['fast_interval_ms']);self.brain.net.store('base12')
        self.restore('base12');self.quiet(wait_before+s['response_ms']+wait_after,'novel','sham_wait')
        self.pulse('novel','sham_A')
        for B in s['B_populations']:
            self.restore('base12');self.quiet(wait_before,B,'pre_B_gap')
            self.pulse(B,'trained_B',label=B)
            self.quiet(wait_after,B,'trained_post_B_gap');self.pulse(B,'trained_after_B')

    def checkpoint(self):
        pd.DataFrame(self.rows).to_csv(self.out/'intervals.csv',index=False)
        if self.rows:pd.DataFrame([r for r in self.rows if r['kind']=='response']).to_csv(self.out/'responses.csv',index=False)
        self.manifest['elapsed_seconds']=time.perf_counter()-self.started
        self.manifest['peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        self.manifest['intervals_sha256']=base.sha(self.out/'intervals.csv')
        if (self.out/'responses.csv').exists():self.manifest['responses_sha256']=base.sha(self.out/'responses.csv')
        base.write_json(self.out/'manifest.json',self.manifest)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--part',choices=['main','novel'],required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();exp=Experiment(args.part,args.output.resolve())
    try:
        for seed in exp.spec['seeds']:
            print('START',args.part,seed,flush=True);exp.prepare(seed)
            if args.part=='main':exp.main_seed()
            else:exp.novel_seed()
            exp.manifest['completed_seeds'].append(seed);exp.checkpoint()
            summary=pd.DataFrame(exp.rows);summary=summary[(summary.seed==seed)&(summary.kind=='response')]
            print('DONE',seed,summary.groupby(['case','phase']).aBN1.apply(list).to_dict(),flush=True)
        exp.manifest['status']='completed'
    except BaseException as error:
        exp.manifest['status']='failed';exp.manifest['error']=repr(error);raise
    finally:exp.checkpoint()
    print('FINISHED',exp.manifest['status'],exp.manifest['elapsed_seconds'],flush=True)


if __name__=='__main__':main()
