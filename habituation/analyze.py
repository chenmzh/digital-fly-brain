#!/usr/bin/env python3
"""Audit raw events before calculating pre-specified habituation metrics."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def metrics(group, p):
    train = group[group.phase == "train"].sort_values("pulse")
    values = train[p["primary_readout"]].to_numpy(dtype=float)
    early = float(values[:p["early_n"]].mean())
    late = float(values[-p["late_n"]:].mean())
    previous = float(values[-2*p["late_n"]:-p["late_n"]].mean())
    initial = float(values[0])
    decrement = 1-late/early if early > 0 else None
    result = {"initial": initial, "early_mean": early, "late_mean": late,
              "decrement_fraction": decrement,
              "h1_screen": bool(decrement is not None and decrement >= p["decrement_threshold"]),
              "plateau_screen": bool(early > 0 and abs(late-previous) <= p["plateau_tolerance_fraction"]*early)}
    for row in group[group.phase == "recovery"].itertuples():
        response = float(getattr(row, p["primary_readout"]))
        label = str(int(row.rest_ms))
        result["probe_" + label] = response
        result["probe_to_initial_" + label] = response/initial if initial > 0 else None
        # Exploratory diagnostic added after inspecting initial batches, not a new H4 pass criterion.
        result["exploratory_recovered_loss_fraction_" + label] = (response-late)/(initial-late) if initial > late else None
    long_response = result["probe_" + str(int(max(p["recovery_ms"])))]
    result["h2_screen"] = bool(result["h1_screen"] and
        long_response-late >= p["recovery_increment_fraction"]*early and
        long_response >= p["recovery_initial_fraction"]*initial)
    return result


def audit_run(path, canonical, known_ids):
    manifest = json.loads((path / "manifest.json").read_text())
    require(manifest["status"] in ["completed", "interrupted"], f"Invalid run status: {path}")
    p = json.loads((path / "protocol.json").read_text())
    for key, value in canonical.items():
        if key not in ["id", "models", "seeds"]:
            require(p.get(key) == value, f"Biological protocol changed: {key}")
    require(set(p["models"]).issubset(canonical["models"]) and set(p["seeds"]).issubset(canonical["seeds"]), "Unexpected subset")
    for rel, digest in manifest["sha256"].items():
        # Historical runner provenance is its immutable per-run snapshot, not a later working copy.
        source = path / "run_snapshot.py" if rel == "habituation/run_experiment.py" else ROOT / rel
        require(sha(source) == digest, f"Source/data changed: {rel}")
    require(sha(path / "run_snapshot.py") == manifest["sha256"]["habituation/run_experiment.py"], "Source snapshot mismatch")
    files = {item["file"]: item for item in manifest["files"]}
    for name, item in files.items():
        require(sha(path / name) == item["sha256"], f"File changed: {path/name}")
    d = pd.read_csv(path / "responses.csv")
    inputs = json.loads((path / "neuron_ids.json").read_text())
    input_ids = np.array([int(x) for x in inputs["input"]], dtype=np.int64)
    require(len(input_ids) == 70 and set(input_ids).issubset(known_ids), "Input IDs invalid")
    readouts = {k: int(v) for k, v in inputs["readouts"].items()}
    dt = p["dt_ms"] / 1000
    signatures = {}
    verified_files = set()
    for (variant, seed, interval), group in d.groupby(["model", "seed", "interval_ms"]):
        require(variant in p["models"] and seed in p["seeds"] and interval in p["onset_intervals_ms"], "Unexpected sequence")
        train = group[group.phase == "train"].sort_values("pulse")
        recovery = group[group.phase == "recovery"]
        require(list(train.pulse) == list(range(p["n_pulses"])), "Incomplete training sequence")
        require(sorted(recovery.rest_ms) == sorted(p["recovery_ms"]), "Incomplete recovery branches")
        require(len(group) == p["n_pulses"]+len(p["recovery_ms"]), "Extra rows")
        pattern = np.load(path / f"pattern_seed{seed}.npz")
        require(len(pattern["tick"]) == int(group.input_events.iloc[0]), "Input event count mismatch")
        require(group.input_events.nunique() == 1, "Changing input intensity")
        key = f"{variant}_s{seed}_T{int(interval)}"
        for phase, sub, filename in [("train", train, key+"_train.parquet")]+[
                ("recovery", recovery[recovery.rest_ms == rest], key+f"_rest{int(rest)}.parquet") for rest in p["recovery_ms"]]:
            require(filename in files, f"Uncheckpointed file is not eligible: {filename}")
            events = pd.read_parquet(path / filename)
            require(events.flywire_id.dtype == np.dtype("int64"), "ID precision lost")
            require(events.flywire_id.isin(known_ids).all(), "Unknown spike ID")
            require(np.isfinite(events.t_s).all() and (events.t_s >= 0).all(), "Invalid spike times")
            ticks = np.rint(events.t_s.to_numpy()/dt).astype(np.int64)
            require(np.allclose(events.t_s.to_numpy()/dt, ticks, atol=1e-7, rtol=0), "Off-grid events")
            require(not events.duplicated(["t_s", "flywire_id"]).any(), "Duplicate events")
            for row in sub.itertuples():
                expected_onset = row.pulse*interval/1000 if phase == "train" else (
                    (p["n_pulses"]-1)*interval/1000+p["response_ms"]/1000+row.rest_ms/1000)
                require(np.isclose(row.onset_s, expected_onset, atol=1e-8, rtol=0), "Incorrect timing")
                begin = round(row.onset_s/dt)
                end = begin+round(p["response_ms"]/p["dt_ms"])
                chosen = (ticks >= begin) & (ticks < end)
                window_ids = events.flywire_id.to_numpy()[chosen]
                require(len(window_ids) == row.total_spikes, "Total spike mismatch")
                for name, neuron_id in readouts.items():
                    require(int((window_ids == neuron_id).sum()) == getattr(row, name), "Readout mismatch")
                sensory = np.isin(window_ids, input_ids)
                require(int(sensory.sum()) == row.sensory_spikes, "Sensory spike mismatch")
                # Compare exact sensory-neuron events, not just commanded input counts.
                pairs = sorted(zip(window_ids[sensory].tolist(), (ticks[chosen][sensory]-begin).tolist()))
                signature = hashlib.sha256(repr(pairs).encode()).hexdigest()
                signatures.setdefault(int(seed), set()).add(signature)
                require(0 <= row.resource_before <= 1+1e-12 and 0 <= row.resource_after <= 1+1e-12, "Resource out of bounds")
            verified_files.add(filename)
    return d, signatures, len(verified_files), manifest


def write_svg(d, p, path):
    """Small dependency-free plot: no smoothing or fitted habituation curves."""
    width, height = 840, 440
    left, top, plotw, ploth = 70, 55, 700, 285
    ymax = max(12, int(d[p["primary_readout"]].max())+1)
    def xy(n, y):
        return left+(n-1)*plotw/(p["n_pulses"]-1), top+ploth-y/ymax*ploth
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<g font-family="sans-serif" font-size="13" fill="#222">',
             '<text x="70" y="25" font-size="18">JO-CE repeated input: aBN1 spikes per 300 ms response window</text>']
    for y in range(0, ymax+1, 2):
        _, yy = xy(1,y)
        lines += [f'<path d="M{left} {yy}h{plotw}" stroke="#ddd"/>', f'<text x="42" y="{yy+4}">{y}</text>']
    colors = ["#222222", "#777777", "#ce3b37", "#2166ac"]
    for index, ((variant, interval), g) in enumerate(d[d.phase == "train"].groupby(["model", "interval_ms"])):
        agg = g.groupby("pulse")[p["primary_readout"]].agg(["mean", "min", "max"])
        pts = [xy(int(n)+1, r["mean"]) for n,r in agg.iterrows()]
        polygon = [xy(int(n)+1,r["min"]) for n,r in agg.iterrows()]+[xy(int(n)+1,r["max"]) for n,r in agg.iloc[::-1].iterrows()]
        color=colors[index]
        lines.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in polygon)}" fill="{color}" opacity="0.12"/>')
        dash=' stroke-dasharray="5 4"' if index==1 else ''
        lines.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in pts)}" fill="none" stroke="{color}" stroke-width="2"{dash}/>')
        for x,y in pts:
            lines.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{color}"/>')
        lines.append(f'<text x="{70+(index%2)*360}" y="{380+(index//2)*20}" fill="{color}">{variant}, onset interval {interval/1000:g} s</text>')
    for n in range(1,p["n_pulses"]+1):
        x,y=xy(n,0);lines.append(f'<text x="{x-4}" y="{y+20}">{n}</text>')
    lines += ['<text x="640" y="365">Stimulus number</text>',
              '<text x="70" y="430">Means and min-max bands across 5 input realizations; not 5 biological flies.</text>', '</g></svg>']
    path.write_text("\n".join(lines)+"\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args()
    args.runs=[path.resolve() for path in args.runs]
    p=json.loads((HERE/"protocols/main_v1.json").read_text())
    known_ids=set(pd.read_csv(ROOT/"upstream/Drosophila_brain_model/2023_03_23_completeness_630_final.csv",index_col=0).index)
    frames=[]; signatures={}; checked=0; sources=[]
    for path in args.runs:
        d,s,n,m=audit_run(path,p,known_ids)
        frames.append(d);checked+=n
        for seed, values in s.items(): signatures.setdefault(seed,set()).update(values)
        sources.append({"path":str(path.relative_to(ROOT)),"status":m["status"],"manifest_sha256":sha(path/"manifest.json"),
                        "responses_sha256":sha(path/"responses.csv"),"checkpoint_elapsed_seconds":m.get("elapsed_seconds"),
                        "peak_rss_mib":m.get("process_peak_rss_mib")})
    d=pd.concat(frames,ignore_index=True)
    keys=["model","seed","interval_ms","phase","pulse","rest_ms"]
    require(not d.duplicated(keys).any(),"Duplicate records across run batches")
    actual=set(d.groupby(["model","seed","interval_ms"]).groups)
    expected=set(itertools.product(p["models"],p["seeds"],p["onset_intervals_ms"]))
    require(actual==expected,"Incomplete canonical experiment")
    require(len(d)==len(expected)*(p["n_pulses"]+len(p["recovery_ms"])),"Wrong total response count")
    require(all(len(s)==1 for s in signatures.values()),"Sensory spikes differ across exposures/models/intervals")
    rows=[]
    for (variant,seed,interval),g in d.groupby(["model","seed","interval_ms"]):
        rows.append({"model":variant,"seed":int(seed),"interval_ms":float(interval),**metrics(g,p)})
    per=pd.DataFrame(rows)
    summary=[]
    for (variant,interval),g in per.groupby(["model","interval_ms"]):
        record={"model":variant,"interval_ms":float(interval),"n":len(g),
                "h1_screen_count":int(g.h1_screen.sum()),"h2_screen_count":int(g.h2_screen.sum()),
                "plateau_screen_count":int(g.plateau_screen.sum())}
        for metric in ["initial","early_mean","late_mean","decrement_fraction","probe_2000","probe_10000",
                       "probe_to_initial_2000","probe_to_initial_10000"]:
            record[metric+"_mean"]=float(g[metric].mean())
            record[metric+"_min"]=float(g[metric].min())
            record[metric+"_max"]=float(g[metric].max())
        summary.append(record)
    report={"scope":p["note"],"sources":sources,"protocol_sha256":sha(HERE/"protocols/main_v1.json"),
            "analysis_source_sha256":sha(Path(__file__)),
            "runner_snapshot_sha256":{str(x.relative_to(ROOT)):sha(x/"run_snapshot.py") for x in args.runs},
            "current_runner_sha256":sha(HERE/"run_experiment.py"),
            "audit":{"complete_sequences":len(expected),"response_windows":len(d),"raw_event_files_checked":checked,
                     "source_data_output_hashes_verified":True,"sensory_event_trains_identical_within_seed":True,
                     "counts_recomputed_from_raw_spikes":True,"interrupted_run_uses_only_checkpointed_sequences":True},
            "descriptive_results":summary}
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    d.to_csv(out/"responses.csv",index=False);per.to_csv(out/"metrics_by_seed.csv",index=False)
    pd.DataFrame(summary).to_csv(out/"summary.csv",index=False)
    write_svg(d,p,out/"training_responses.svg")
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
