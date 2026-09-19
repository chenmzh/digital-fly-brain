#!/usr/bin/env python3
"""One declared H4(b) qualification supplement; original thresholds unchanged."""
import argparse
import json
from pathlib import Path
from datetime import datetime,timezone
from run import Experiment,base,HERE,pd


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    spec=json.loads((HERE/'frequency_protocol.json').read_text());freeze=json.loads((HERE/'frequency_freeze.json').read_text())
    for name,digest in freeze['source_sha256'].items():base.require(base.sha(HERE/name)==digest,'Supplement source changed after freeze')
    out=args.output.resolve();exp=Experiment('frequency',out);exp.spec=spec
    base.write_json(out/'protocol.json',spec);(out/'entrypoint_snapshot.py').write_bytes(Path(__file__).read_bytes())
    for path in [Path(__file__),HERE/'frequency_protocol.json',HERE/'FREQUENCY_SUPPLEMENT.md',HERE/'frequency_freeze.json',HERE/'analysis/full/report.json']:
        exp.manifest['source_sha256'][str(path.relative_to(base.ROOT))]=base.sha(path)
    exp.manifest['extension']='H4b qualification: T=750ms and 24 pulses, paired to existing fast24'
    exp.manifest['supplement_started_utc']=datetime.now(timezone.utc).isoformat();exp.checkpoint()
    try:
        for seed in spec['seeds']:
            print('START frequency',seed,flush=True);exp.prepare(seed);exp.restore('initial')
            exp.train('frequency24',spec['slow_interval_ms'],end=spec['n_train'])
            exp.brain.net.store('trained');exp.recovery('trained','frequency24')
            exp.manifest['completed_seeds'].append(seed);exp.checkpoint()
            d=pd.DataFrame(exp.rows);d=d[(d.seed==seed)&(d.kind=='response')]
            print('DONE',seed,d.groupby('phase').aBN1.apply(list).to_dict(),flush=True)
        exp.manifest['status']='completed'
    except BaseException as error:
        exp.manifest['status']='failed';exp.manifest['error']=repr(error);raise
    finally:exp.checkpoint()
    print('FINISHED',exp.manifest['status'],exp.manifest['elapsed_seconds'],flush=True)


if __name__=='__main__':main()
