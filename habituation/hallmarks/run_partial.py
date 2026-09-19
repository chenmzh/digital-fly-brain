#!/usr/bin/env python3
"""One prospectively specified H3 partial-recovery extension; no parameter search."""
import argparse
import json
from pathlib import Path
from datetime import datetime,timezone
from run import Experiment,base,HERE,pd


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    spec=json.loads((HERE/'partial_protocol.json').read_text());freeze=json.loads((HERE/'partial_freeze.json').read_text())
    for name,digest in freeze['source_sha256'].items():base.require(base.sha(HERE/name)==digest,'Supplement changed after freeze')
    out=args.output.resolve();exp=Experiment('partial',out)
    exp.spec=spec
    base.write_json(out/'protocol.json',spec)
    (out/'entrypoint_snapshot.py').write_bytes(Path(__file__).read_bytes())
    for path in [Path(__file__),HERE/'partial_protocol.json',HERE/'H3_PARTIAL_RECOVERY.md',HERE/'partial_freeze.json']:
        exp.manifest['source_sha256'][str(path.relative_to(base.ROOT))]=base.sha(path)
    exp.manifest['extension']='H3 with 2-second partial recovery; original 10-second protocol unchanged'
    exp.manifest['supplement_started_utc']=datetime.now(timezone.utc).isoformat();exp.checkpoint()
    try:
        for seed in spec['seeds']:
            print('START partial',seed,flush=True);exp.prepare(seed);exp.restore('initial')
            for block in range(1,4):
                if block>1:exp.quiet(spec['between_cycles_ms'],'h3_partial','cycle_rest',block=block)
                exp.train('h3_partial',spec['fast_interval_ms'],block=block)
            exp.manifest['completed_seeds'].append(seed);exp.checkpoint()
            d=pd.DataFrame(exp.rows);d=d[(d.seed==seed)&(d.kind=='response')]
            print('DONE',seed,d.groupby('block').aBN1.apply(list).to_dict(),flush=True)
        exp.manifest['status']='completed'
    except BaseException as error:
        exp.manifest['status']='failed';exp.manifest['error']=repr(error);raise
    finally:exp.checkpoint()
    print('FINISHED',exp.manifest['status'],exp.manifest['elapsed_seconds'],flush=True)


if __name__=='__main__':main()
