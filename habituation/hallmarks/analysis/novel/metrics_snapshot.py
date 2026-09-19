"""Prespecified descriptive screens; no fitting and no biological p-values."""
import math
import numpy as np


def train_metrics(values,minimum=5,threshold=.3,tolerance=.1):
    v=np.asarray(values,dtype=float);first=float(v[0]);early=float(v[:3].mean());late=float(v[-3:].mean())
    previous=float(v[-6:-3].mean());D=1-late/early if early>0 else None
    half=next((i+1 for i in range(len(v)-2) if np.all(v[i:i+3]<=.5*first)),None) if first>0 else None
    return {'initial':first,'early':early,'late':late,'D':D,'initial_usable':first>=minimum,
            'decrement':D is not None and D>=threshold,'plateau':early>0 and abs(previous-late)<=tolerance*early,'half_trial':half}


def threshold_bracket(times,values,threshold):
    """First sampled crossing; a true time bound additionally needs monotonicity."""
    t=np.asarray(times,dtype=float);v=np.asarray(values,dtype=float)
    if not np.isfinite(v).all():return {'lower_ms':None,'upper_ms':None,'monotone':False,'status':'undefined'}
    monotone=bool(np.all(np.diff(v)>=-1e-12))
    indices=np.flatnonzero(v>=threshold)
    if len(indices):
        k=int(indices[0]);return {'lower_ms':float(t[k-1]) if k else 0.,'upper_ms':float(t[k]),'monotone':monotone,'status':'crossed'}
    return {'lower_ms':float(t[-1]),'upper_ms':None,'monotone':monotone,'status':'right_censored'}


def strictly_earlier(a,b):
    return bool(a['monotone'] and b['monotone'] and a['upper_ms'] is not None and b['lower_ms'] is not None and a['upper_ms']<=b['lower_ms'])


def recovery_metrics(train,times,probes):
    first=train['initial'];late=train['late'];y=np.asarray(probes,dtype=float)
    fraction=(y-late)/(first-late) if first>late else np.full(len(y),np.nan)
    relative=y/first if first>0 else np.full(len(y),np.nan)
    return {'F':[float(x) if math.isfinite(x) else None for x in fraction],
            'relative_initial':[float(x) if math.isfinite(x) else None for x in relative],
            'half_lost':threshold_bracket(times,fraction,.5),'eighty_initial':threshold_bracket(times,relative,.8)}


def h3_screen(blocks):
    a,b,c=blocks
    usable=all(x['initial_usable'] for x in blocks) and all(x['initial']>=.8*a['initial'] for x in blocks[1:])
    extent=all(x['D'] is not None for x in blocks) and b['D']>=a['D'] and c['D']>=b['D'] and c['D']-a['D']>=.1-1e-12
    speed=all(x['half_trial'] is not None for x in blocks) and b['half_trial']<=a['half_trial'] and c['half_trial']<=b['half_trial'] and c['half_trial']<=a['half_trial']-1
    return {'eligible':bool(usable and a['decrement']),'extent_enhancement':bool(extent),'speed_enhancement':bool(speed),
            'supported':bool(usable and a['decrement'] and (extent or speed))}


def expected_schedule(part,spec):
    rows=[];clock=0.
    def add(kind,ms,case,phase,block=0,pulse=-1,rest_ms=0,label='blank',hz=150.):
        nonlocal clock
        rows.append({'kind':kind,'case':case,'phase':phase,'block':block,'pulse':pulse,'rest_ms':rest_ms,'label':label,
                     'input_hz':hz if label!='blank' else 0.,'onset_s':clock/1000,'duration_ms':ms})
        clock+=ms
    def train(case,T,block=1,start=0,end=12,hz=150.,first_gap=False):
        for k in range(start,end):
            if k>start or first_gap:add('quiet',T-300,case,'gap',block,k)
            add('response',300,case,'train',block,k,label='A',hz=hz)
    def recover(state,case):
        nonlocal clock
        for rest in spec['recovery_ms']:
            clock=state;add('quiet',rest,case,'rest',rest_ms=rest)
            add('response',300,case,'recovery',rest_ms=rest,label='A')
    if part=='main':
        train('fast12',500);trained=clock;recover(trained,'fast12')
        clock=trained
        for block in [2,3]:
            add('quiet',10000,'h3','cycle_rest',block);train('h3',500,block)
        clock=trained;train('fast24',500,start=12,end=24,first_gap=True);recover(clock,'fast24')
        clock=0.;train('slow12',1000);recover(clock,'slow12')
        clock=0.;train('strong12',500,hz=200.)
    else:
        add('quiet',500,'novel','naive_wait');add('response',300,'novel','naive_A',label='A')
        for B in spec['B_populations']:
            clock=0.;add('response',300,B,'naive_B',label=B)
            add('quiet',200,B,'post_B_gap');add('response',300,B,'naive_after_B',label='A')
            clock=300.;add('quiet',200,B,'blank_gap');add('response',300,B,'blank_after_B')
        clock=0.;train('novel_train',500);trained=clock
        add('quiet',700,'novel','sham_wait');add('response',300,'novel','sham_A',label='A')
        for B in spec['B_populations']:
            clock=trained;add('quiet',200,B,'pre_B_gap');add('response',300,B,'trained_B',label=B)
            add('quiet',200,B,'trained_post_B_gap');add('response',300,B,'trained_after_B',label='A')
    return rows
